import type { TraceEvent } from "./types";

export const AGENTS = [
  "orchestrator", "present", "past", "supply", "strategist", "sentinel", "auditor", "liaison",
] as const;
export type AgentId = (typeof AGENTS)[number];

export function sortByTs(events: TraceEvent[]): TraceEvent[] {
  return events
    .map((e, i) => ({ e, i }))
    .sort((a, b) => Date.parse(a.e.ts) - Date.parse(b.e.ts) || a.i - b.i)
    .map(({ e }) => e);
}

/** Each agent lane holds every event the agent sent or received, in time order. */
export function groupByLane(events: TraceEvent[]): Record<AgentId, TraceEvent[]> {
  const lanes = Object.fromEntries(AGENTS.map((a) => [a, [] as TraceEvent[]])) as Record<AgentId, TraceEvent[]>;
  for (const e of sortByTs(events)) {
    for (const agent of new Set([e.from_agent, e.to_agent])) {
      if (agent in lanes) lanes[agent as AgentId].push(e);
    }
  }
  return lanes;
}

export function summarizePayload(payload: Record<string, unknown>, max = 120): string {
  if (!payload || Object.keys(payload).length === 0) return "";
  let s: string;
  if (typeof payload.text === "string") s = payload.text;
  else if (typeof payload.tool === "string") s = payload.tool;
  else s = JSON.stringify(payload);
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}
