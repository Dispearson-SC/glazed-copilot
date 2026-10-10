import { sanitizeReply } from "./sanitize";
import { parseTraceMessage } from "./parseTraceMessage";
import { sortByTs } from "./trace";
import type { ReplyMeta, TraceEvent, TurnRecord } from "./types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "error";
  text: string;
  /** Only set for replies produced in the current session; trace events carry no turn_id. */
  turnId?: string;
  meta?: ReplyMeta | null;
  /** Question to resend when the user retries an error bubble. */
  retryText?: string;
  /** Earlier orchestrator responses of the same exchange (e.g. "Consulto a abastecimiento…"). */
  steps?: string[];
  /** The backend clipped the stored message. */
  truncated?: boolean;
  /** ISO time: the stored turn timestamp, or the moment a local message was created. */
  ts?: string;
}

const MANAGER = "manager";
const ORCHESTRATOR = "orchestrator";

interface Exchange {
  user?: { text: string; truncated: boolean };
  responses: Array<{ text: string; truncated: boolean }>;
}

/**
 * Rebuilds the visible conversation from trace events: manager <-> orchestrator messages only.
 * Each real manager request starts an exchange; every orchestrator response up to the next
 * request is collapsed into one bubble (the last response), earlier ones become `steps`.
 */
export function buildHistory(events: TraceEvent[]): ChatMessage[] {
  const exchanges: Exchange[] = [];
  for (const e of sortByTs(events)) {
    if (e.kind !== "message" || typeof e.payload?.text !== "string") continue;
    const fromUser = e.from_agent === MANAGER && e.to_agent === ORCHESTRATOR;
    const fromBot = e.from_agent === ORCHESTRATOR && e.to_agent === MANAGER;
    if (!fromUser && !fromBot) continue;
    const { text, truncated, untrusted } = parseTraceMessage(e.payload.text);
    if (!text) continue;
    if (fromUser) {
      if (untrusted) continue; // injected tool output is not something the manager said
      exchanges.push({ user: { text, truncated }, responses: [] });
    } else {
      if (exchanges.length === 0) exchanges.push({ responses: [] });
      exchanges[exchanges.length - 1].responses.push({ text, truncated });
    }
  }
  const out: ChatMessage[] = [];
  exchanges.forEach((x, i) => {
    if (x.user) out.push({ id: `h-${i}-u`, role: "user", text: x.user.text, ...(x.user.truncated ? { truncated: true } : {}) });
    const last = x.responses.at(-1);
    if (!last) return;
    const steps = x.responses.slice(0, -1).map((r) => r.text);
    out.push({
      id: `h-${i}-a`,
      role: "assistant",
      text: last.text,
      ...(last.truncated ? { truncated: true } : {}),
      ...(steps.length ? { steps } : {}),
    });
  });
  return out;
}

export const WORKING_TEXT = "El copiloto sigue trabajando…";

/** Rebuilds the conversation from the stored turns (full replies, ordered by ts). Back-filled rows may carry serialized envelopes. */
export function buildTurnHistory(turns: TurnRecord[]): ChatMessage[] {
  const out: ChatMessage[] = [];
  for (const t of [...turns].sort((a, b) => a.ts.localeCompare(b.ts))) {
    const user = parseTraceMessage(t.user_text ?? "");
    out.push({ id: `s-${t.turn_id}-u`, role: "user", text: user.text, ts: t.ts, ...(user.truncated ? { truncated: true } : {}) });
    if (t.status === "failed") {
      out.push({ id: `s-${t.turn_id}-e`, role: "error", text: t.error || "El copiloto no pudo responder.", retryText: user.text });
      continue;
    }
    const raw = t.reply?.trim();
    const hasReply = t.status !== "pending" && !!raw && raw !== "None";
    if (!hasReply) {
      if (t.status === "pending") out.push({ id: `s-${t.turn_id}-a`, role: "assistant", text: WORKING_TEXT, turnId: t.turn_id });
      continue;
    }
    const reply = parseTraceMessage(raw!);
    out.push({ id: `s-${t.turn_id}-a`, role: "assistant", text: reply.text, ts: t.ts, turnId: t.turn_id, meta: t.reply_meta, ...(reply.truncated ? { truncated: true } : {}) });
  }
  return out;
}
