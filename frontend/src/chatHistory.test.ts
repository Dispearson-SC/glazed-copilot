import { describe, expect, it } from "vitest";
import { buildHistory, buildTurnHistory } from "./chatHistory";
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

describe("buildTurnHistory", () => {
  const turn = (over = {}) => ({ turn_id: "t1", ts: "2026-03-01T10:00:00Z", user_text: "¿Qué pido?", reply: "Pide 40", status: "done" as const, ...over });

  it("turns each stored turn into a user bubble and an assistant bubble with its turn id", () => {
    const h = buildTurnHistory([turn(), turn({ turn_id: "t2", ts: "2026-03-01T09:00:00Z", user_text: "hola", reply: "buenas" })]);
    expect(h.map((m) => [m.role, m.text])).toEqual([["user", "hola"], ["assistant", "buenas"], ["user", "¿Qué pido?"], ["assistant", "Pide 40"]]);
    expect(h[1]).toMatchObject({ turnId: "t2" });
  });

  it("sanitizes thinking markup and keeps reply_meta", () => {
    const [, a] = buildTurnHistory([turn({ reply: "<think>x</think>Listo", reply_meta: { source: "fast", elapsed_ms: 900 } })]);
    expect(a.text).toBe("Listo");
    expect(a.meta).toEqual({ source: "fast", elapsed_ms: 900 });
  });

  const ENVELOPE = '{"kind": "request", "parts": [{"content": "¿Qué tengo que pedir hoy y qué se me puede agotar esta semana?", "part_kind": "user-prompt", "timestamp": "2026-10-10';

  it("unwraps a back-filled user_text that is a serialized (clipped) envelope", () => {
    const [u] = buildTurnHistory([turn({ user_text: ENVELOPE })]);
    expect(u.text).toBe("¿Qué tengo que pedir hoy y qué se me puede agotar esta semana?");
    expect(u.truncated).toBe(true);
  });

  it("unwraps a complete envelope in reply and leaves plain text unchanged", () => {
    const reply = JSON.stringify({ kind: "response", parts: [{ content: "Pide 40" }] });
    expect(buildTurnHistory([turn({ reply })])[1].text).toBe("Pide 40");
    expect(buildTurnHistory([turn({ reply: "## Título\n**negrita**" })])[1].text).toBe("## Título\n**negrita**");
  });

  it("renders pending rows as working, never as None, whatever the reply holds", () => {
    for (const reply of [null, "None", ""]) {
      const h = buildTurnHistory([turn({ status: "pending", reply })]);
      expect(h[1]).toMatchObject({ role: "assistant", text: "El copiloto sigue trabajando…" });
      expect(h.some((m) => m.text === "None")).toBe(false);
    }
  });

  it("shows a failed turn as an error that can be retried", () => {
    const h = buildTurnHistory([turn({ status: "failed", reply: null, error: "Core caído" }), turn({ turn_id: "t3", ts: "2026-03-01T11:00:00Z", status: "pending", reply: null, still_running: true })]);
    expect(h[1]).toMatchObject({ role: "error", text: "Core caído", retryText: "¿Qué pido?" });
    expect(h.filter((m) => m.role === "user")).toHaveLength(2);
  });
});

describe("message time", () => {
  it("carries the stored turn timestamp on both bubbles", () => {
    const [u, a] = buildTurnHistory([{ turn_id: "t1", ts: "2026-03-01T10:00:00Z", user_text: "hola", reply: "buenas", status: "done" }]);
    expect(u.ts).toBe("2026-03-01T10:00:00Z");
    expect(a.ts).toBe("2026-03-01T10:00:00Z");
  });
});
