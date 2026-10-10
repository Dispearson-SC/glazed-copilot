import { sortByTs } from "./trace";
import type { ReplyMeta, TraceEvent } from "./types";
import { sanitizeReply } from "./sanitize";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "error";
  text: string;
  /** Only set for replies produced in the current session; trace events carry no turn id. */
  turnId?: string;
  meta?: ReplyMeta | null;
  /** Question to resend when the user retries an error bubble. */
  retryText?: string;
}

const MANAGER = "manager";
const ORCHESTRATOR = "orchestrator";

/** Rebuilds the visible conversation from trace events: manager <-> orchestrator messages only. */
export function buildHistory(events: TraceEvent[]): ChatMessage[] {
  const out: ChatMessage[] = [];
  sortByTs(events).forEach((e, i) => {
    if (e.kind !== "message" || typeof e.payload?.text !== "string") return;
    const fromUser = e.from_agent === MANAGER && e.to_agent === ORCHESTRATOR;
    const fromBot = e.from_agent === ORCHESTRATOR && e.to_agent === MANAGER;
    if (!fromUser && !fromBot) return;
    const text = fromBot ? sanitizeReply(e.payload.text) : e.payload.text.trim();
    if (!text) return;
    out.push({ id: `h-${i}`, role: fromUser ? "user" : "assistant", text });
  });
  return out;
}
