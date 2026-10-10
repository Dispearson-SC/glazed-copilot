import { describe, expect, it } from "vitest";
import { AGENTS, groupByLane, sortByTs, summarizePayload } from "./trace";
import type { TraceEvent } from "./types";

const ev = (ts: string, from: string, to: string, kind: TraceEvent["kind"] = "message", payload = {}): TraceEvent => ({
  case_id: "c1",
  store_id: "S030",
  ts,
  from_agent: from,
  to_agent: to,
  kind,
  payload,
});

describe("trace helpers", () => {
  it("lists the eight agents with orchestrator first", () => {
    expect(AGENTS).toEqual([
      "orchestrator", "present", "past", "supply", "strategist", "sentinel", "auditor", "liaison",
    ]);
  });

  it("sorts chronologically without mutating the input", () => {
    const input = [
      ev("2026-03-01T10:00:02Z", "present", "orchestrator"),
      ev("2026-03-01T10:00:00Z", "manager", "orchestrator"),
      ev("2026-03-01T10:00:01Z", "orchestrator", "present"),
    ];
    const sorted = sortByTs(input);
    expect(sorted.map((e) => e.ts)).toEqual([
      "2026-03-01T10:00:00Z", "2026-03-01T10:00:01Z", "2026-03-01T10:00:02Z",
    ]);
    expect(input[0].ts).toBe("2026-03-01T10:00:02Z");
  });

  it("groups events into each involved agent's lane, ordered by ts", () => {
    const events = [
      ev("2026-03-01T10:00:02Z", "present", "orchestrator", "tool_result"),
      ev("2026-03-01T10:00:00Z", "manager", "orchestrator"),
      ev("2026-03-01T10:00:01Z", "orchestrator", "present", "tool_call"),
    ];
    const lanes = groupByLane(events);
    expect(lanes.orchestrator.map((e) => e.kind)).toEqual(["message", "tool_call", "tool_result"]);
    expect(lanes.present.map((e) => e.kind)).toEqual(["tool_call", "tool_result"]);
    expect(lanes.supply).toEqual([]);
  });

  it("does not duplicate self-addressed events and ignores unknown agents as lanes", () => {
    const lanes = groupByLane([ev("2026-03-01T10:00:00Z", "supply", "supply", "tool_call")]);
    expect(lanes.supply).toHaveLength(1);
    expect(Object.keys(lanes)).toEqual([...AGENTS]);
  });

  it("summarizes payloads: text, tool name, or truncated JSON", () => {
    expect(summarizePayload({ text: "hola" })).toBe("hola");
    expect(summarizePayload({ tool: "kpis", args: {} })).toBe("kpis");
    expect(summarizePayload({ a: 1 })).toBe('{"a":1}');
    expect(summarizePayload({ text: "x".repeat(200) }, 20)).toBe("x".repeat(19) + "…");
    expect(summarizePayload({})).toBe("");
  });
});
