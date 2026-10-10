import { describe, expect, it } from "vitest";
import { sortByTs } from "./trace";
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
});
