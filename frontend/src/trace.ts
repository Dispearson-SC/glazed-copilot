import type { TraceEvent } from "./types";

export function sortByTs(events: TraceEvent[]): TraceEvent[] {
  return events
    .map((e, i) => ({ e, i }))
    .sort((a, b) => Date.parse(a.e.ts) - Date.parse(b.e.ts) || a.i - b.i)
    .map(({ e }) => e);
}
