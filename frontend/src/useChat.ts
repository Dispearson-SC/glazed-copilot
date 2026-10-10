import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "./ApiContext";
import { ApiError } from "./api";
import { buildHistory, buildTurnHistory, type ChatMessage } from "./chatHistory";
import { parseTraceMessage } from "./parseTraceMessage";
import { sanitizeReply } from "./sanitize";
import type { Proposal, TurnRecord } from "./types";

export type ChatStatus = "idle" | "working" | "waiting_approval";

export interface UseChatOptions {
  storeId?: string;
  /** Lazy start: nothing is fetched until true. */
  enabled?: boolean;
  pollMs?: number;
  /** How long a 404 on a fresh turn is treated as "still queued". */
  notFoundGraceMs?: number;
}

/** A finished turn is never pending, whatever its reply: only the backend status says it is still running. */
const isPendingTurn = (t: TurnRecord) => t.status === "pending";

const NO_TEXT_REPLY = "El copiloto terminó sin respuesta de texto. Revisa el razonamiento.";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function useChat(caseId: string, opts: UseChatOptions = {}) {
  const { storeId = "", enabled = true, pollMs = 2500, notFoundGraceMs = 30_000 } = opts;
  const api = useApi();
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [local, setLocal] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [stillRunning, setStillRunning] = useState(false);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [decisionError, setDecisionError] = useState<Error | null>(null);
  const run = useRef(0); // bumped to cancel any in-flight polling loop
  const seq = useRef(0);
  const lastText = useRef("");

  const refreshProposals = useCallback(async () => {
    if (!caseId) return;
    try {
      const all = await api.listProposals({ case_id: caseId, status: "pending" });
      setProposals(all.filter((p) => p.status === "pending"));
    } catch {
      /* keep the last list; the next refresh retries */
    }
  }, [api, caseId]);

  useEffect(() => {
    run.current++;
    setHistory([]);
    setLocal([]);
    setStatus("idle");
    setStillRunning(false);
    setProposals([]);
    if (!enabled || !caseId) return;
    let alive = true;
    const patch = (id: string, next: ChatMessage) => setHistory((h) => h.map((m) => (m.id === id ? next : m)));
    // A pending stored turn has no live poller after a reload: resume it like a fresh one.
    const resumeTurn = async (turn: TurnRecord) => {
      const startedAt = Date.now();
      const id = `s-${turn.turn_id}-a`;
      const userText = parseTraceMessage(turn.user_text ?? "").text;
      const fail = (msg: string) => {
        setStillRunning(false);
        patch(id, { id: `s-${turn.turn_id}-e`, role: "error", text: msg, retryText: userText });
      };
      while (alive) {
        try {
          const t = await api.getTurn(caseId, turn.turn_id);
          if (!alive) return;
          if (t.status === "pending") {
            setStillRunning(Boolean(t.still_running));
          } else {
            setStillRunning(false);
            if (t.status === "failed") return fail(t.error || "El copiloto no pudo responder.");
            const raw = t.reply?.trim();
            if (raw && raw !== "None") {
              const reply = parseTraceMessage(raw);
              patch(id, { id, role: "assistant", text: reply.text, turnId: turn.turn_id, meta: t.reply_meta, ...(reply.truncated ? { truncated: true } : {}) });
            } else {
              patch(id, { id, role: "assistant", text: NO_TEXT_REPLY, turnId: turn.turn_id, meta: t.reply_meta });
            }
            await refreshProposals();
            return;
          }
        } catch (e) {
          const queued = e instanceof ApiError && e.status === 404 && Date.now() - startedAt < notFoundGraceMs;
          if (!queued) return alive ? fail((e as Error).message) : undefined;
        }
        await sleep(pollMs);
      }
    };
    // Stored turns carry the full replies; the trace parser is the fallback while the route is missing or empty.
    api
      .listTurns(caseId)
      .then((turns) => {
        if (turns.length === 0) throw new Error("no stored turns");
        if (!alive) return;
        setHistory(buildTurnHistory(turns));
        turns.filter(isPendingTurn).forEach((t) => void resumeTurn(t));
      })
      .catch(() =>
        api.getTrace(storeId, caseId).then((ev) => alive && setHistory(buildHistory(ev))).catch(() => {}),
      );
    void refreshProposals();
    return () => {
      alive = false;
      run.current++;
    };
  }, [api, caseId, storeId, enabled, refreshProposals, pollMs, notFoundGraceMs]);

  const addLocal = (m: Omit<ChatMessage, "id">) => setLocal((l) => [...l, { ...m, id: `l-${++seq.current}` }]);

  const pollTurn = useCallback(
    async (turnId: string, text: string, token: number) => {
      const startedAt = Date.now();
      const fail = (msg: string) => {
        addLocal({ role: "error", text: msg, retryText: text });
        setStatus("idle");
        setStillRunning(false);
      };
      while (run.current === token) {
        try {
          const t = await api.getTurn(caseId, turnId);
          if (run.current !== token) return;
          if (t.status === "pending") {
            setStillRunning(Boolean(t.still_running));
          } else {
            setStillRunning(false);
            if (t.status === "failed") return fail(t.error || "El copiloto no pudo responder.");
            if (t.reply) addLocal({ role: "assistant", text: sanitizeReply(t.reply), turnId, meta: t.reply_meta });
            setStatus(t.status === "waiting_approval" ? "waiting_approval" : "idle");
            await refreshProposals();
            return;
          }
        } catch (e) {
          const queued = e instanceof ApiError && e.status === 404 && Date.now() - startedAt < notFoundGraceMs;
          if (!queued) return run.current === token ? fail((e as Error).message) : undefined;
        }
        await sleep(pollMs);
      }
    },
    [api, caseId, pollMs, notFoundGraceMs, refreshProposals],
  );

  const submit = useCallback(
    async (text: string, isRetry: boolean) => {
      const clean = text.trim();
      if (!clean || !caseId) return;
      const token = ++run.current;
      lastText.current = clean;
      setLocal((l) => l.filter((m) => m.role !== "error"));
      if (!isRetry) addLocal({ role: "user", text: clean });
      setStatus("working");
      setStillRunning(false);
      try {
        const { turn_id } = await api.sendMessage(caseId, clean);
        await pollTurn(turn_id, clean, token);
      } catch (e) {
        if (run.current !== token) return;
        addLocal({ role: "error", text: (e as Error).message, retryText: clean });
        setStatus("idle");
      }
    },
    [api, caseId, pollTurn],
  );

  const send = useCallback((text: string) => submit(text, false), [submit]);
  const retry = useCallback((text?: string) => submit(text ?? lastText.current, true), [submit]);

  const decide = useCallback(
    async (proposalId: string, approved: boolean, reason?: string) => {
      setDecisionError(null);
      const idempotencyKey = crypto.randomUUID(); // once per click
      try {
        await api.decide(proposalId, approved ? { approved } : { approved, reason }, { idempotencyKey });
      } catch (e) {
        // 409: already decided elsewhere; the refresh below reconciles the list.
        if (!(e instanceof ApiError && e.status === 409)) setDecisionError(e as Error);
      }
      await refreshProposals();
    },
    [api, refreshProposals],
  );

  return {
    messages: [...history, ...local],
    status,
    stillRunning,
    proposals,
    decisionError,
    send,
    retry,
    decide,
  };
}
