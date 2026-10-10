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

  describe("serialized envelopes", () => {
    const U = (ts: string, content: string) =>
      ev(ts, "manager", "orchestrator", "message", { text: JSON.stringify({ kind: "request", parts: [{ content }] }) });
    const R = (ts: string, content: string) =>
      ev(ts, "orchestrator", "manager", "message", { text: JSON.stringify({ kind: "response", parts: [{ id: null, content }] }) });

    it("drops untrusted tool output and collapses responses into one bubble using the last", () => {
      const h = buildHistory([
        ev("2026-03-01T10:00:00Z", "manager", "orchestrator", "message", {
          text: '{"kind": "request", "parts": [{"content": "¿Qué deberíamos pedir mañana y por qu…',
        }),
        ev("2026-03-01T10:00:01Z", "orchestrator", "manager", "message", {
          text: '{"kind": "response", "parts": [{"id": null, "content": "I\'ll consult to glazed_present f…',
        }),
        ev("2026-03-01T10:00:02Z", "manager", "orchestrator", "message", {
          text: '{"kind": "request", "parts": [{"content": "<untrusted-tool-output>\\n## S030 · Pl…',
        }),
        R("2026-03-01T10:00:03Z", "Consulto a abastecimiento…"),
        R("2026-03-01T10:00:04Z", "Pide 40 donas."),
        U("2026-03-01T10:00:05Z", "¿Y mañana?"),
        R("2026-03-01T10:00:06Z", "Igual."),
      ]);
      expect(h.map((m) => [m.role, m.text])).toEqual([
        ["user", "¿Qué deberíamos pedir mañana y por qu…"],
        ["assistant", "Pide 40 donas."],
        ["user", "¿Y mañana?"],
        ["assistant", "Igual."],
      ]);
      expect(h[0].truncated).toBe(true);
      expect(h[1].steps).toEqual(["I'll consult to glazed_present f…", "Consulto a abastecimiento…"]);
      expect(h[3].steps).toBeUndefined();
    });

    it("sanitizes the chosen answer and ignores empty tool-call-only responses", () => {
      const h = buildHistory([
        U("2026-03-01T10:00:00Z", "hola"),
        R("2026-03-01T10:00:01Z", "<think>x</think>Listo"),
        ev("2026-03-01T10:00:02Z", "orchestrator", "manager", "message", { text: '{"kind": "response", "parts": [{"tool_name": "x"}]}' }),
      ]);
      expect(h.map((m) => m.text)).toEqual(["hola", "Listo"]);
    });
  });
});
