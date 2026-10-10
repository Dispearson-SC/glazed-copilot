import { describe, expect, it } from "vitest";
import { buildHistory } from "./chatHistory";
import { ev } from "./test/helpers";

describe("buildHistory", () => {
  it("keeps only manager<->orchestrator messages, ordered by ts", () => {
    const events = [
      ev("2026-03-01T10:00:09Z", "orchestrator", "manager", "message", { text: "Pide 40" }),
      ev("2026-03-01T10:00:00Z", "manager", "orchestrator", "message", { text: "¿Qué pido?" }),
      ev("2026-03-01T10:00:03Z", "orchestrator", "supply", "message", { text: "calcula" }),
      ev("2026-03-01T10:00:04Z", "supply", "orchestrator", "message", { text: "40" }),
      ev("2026-03-01T10:00:05Z", "orchestrator", "supply", "tool_call", { text: "x" }),
      ev("2026-03-01T10:00:06Z", "orchestrator", "manager", "tool_result", { text: "y" }),
    ];
    const h = buildHistory(events);
    expect(h.map((m) => [m.role, m.text])).toEqual([
      ["user", "¿Qué pido?"],
      ["assistant", "Pide 40"],
    ]);
  });
  it("sanitizes replies and skips messages without text", () => {
    const h = buildHistory([
      ev("2026-03-01T10:00:00Z", "manager", "orchestrator", "message", {}),
      ev("2026-03-01T10:00:01Z", "orchestrator", "manager", "message", { text: "<think>x</think>Listo" }),
    ]);
    expect(h).toHaveLength(1);
    expect(h[0].text).toBe("Listo");
  });
  it("never links history items to a turn (trace events carry no turn_id)", () => {
    const h = buildHistory([ev("2026-03-01T10:00:01Z", "orchestrator", "manager", "message", { text: "ok", turn_id: "t9" })]);
    expect(h[0].turnId).toBeUndefined();
  });
  it("keeps order for events with identical timestamps", () => {
    const h = buildHistory([
      ev("2026-03-01T10:00:00Z", "manager", "orchestrator", "message", { text: "q" }),
      ev("2026-03-01T10:00:00Z", "orchestrator", "manager", "message", { text: "a" }),
    ]);
    expect(h.map((m) => m.role)).toEqual(["user", "assistant"]);
  });
});
