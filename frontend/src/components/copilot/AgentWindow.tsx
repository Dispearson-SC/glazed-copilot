import { useEffect, useRef, useState, type FormEvent } from "react";
import { useApi } from "../../ApiContext";
import Markdown from "../../chat/Markdown";
import { consultingText, fetchIssueAnalysis, type AnalysisRef, type AnalysisState, type DecisionItem } from "../../data/copilot";
import { clockTime } from "../../format";
import { useCopilot } from "../../state/copilotStore";
import type { ChatMessage } from "../../chatHistory";
import type { AgentsStatusResponse } from "../../types";
import type { useChat } from "../../useChat";
import AgentOrb from "./AgentOrb";
import AnalysisCard from "./AnalysisCard";
import { ChatSkeleton } from "./Skeleton";
import TransferOptions from "./TransferOptions";
import ConversationBar from "./ConversationBar";

type Chat = ReturnType<typeof useChat>;

/** Suggestion chips of Copiloto.dc.html. */
export const COPILOT_SUGGESTIONS = ["¿Qué pido hoy?", "¿Por qué tiramos tanta dona?", "Resume las advertencias"];

function UserBubble({ m }: { m: ChatMessage }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-[16px_16px_6px_16px] bg-secondary px-4 py-2.5 text-white">
        <p className="m-0 whitespace-pre-wrap font-body-md text-body-md">{m.text}</p>
        {m.ts && <p className="m-0 mt-1 text-right font-label-sm text-label-sm text-white/70">{clockTime(m.ts)}</p>}
      </div>
    </div>
  );
}

function AssistantBubble({ m }: { m: ChatMessage }) {
  const time = clockTime(m.ts);
  return (
    <div className="flex justify-start gap-2">
      <div className="mt-1 flex-shrink-0"><AgentOrb size={28} /></div>
      <div className="min-w-0 max-w-[85%] rounded-[16px_16px_16px_6px] border border-surface-container-high bg-white px-4 py-2.5">
        <div className="text-on-surface"><Markdown text={m.text} /></div>
        {m.truncated && <p className="m-0 font-label-sm text-label-sm text-on-surface-variant">…(recortado)</p>}
        <p className="m-0 mt-1 font-label-sm text-label-sm text-on-surface-variant">Orquestador{time ? ` · ${time}` : ""}</p>
      </div>
    </div>
  );
}

/** Orb status line: 'Listo · N agentes conectados' once /agents/status answers (every agent shares the Core state). */
function agentsLine(a: AgentsStatusResponse | null): string {
  if (!a) return "Listo";
  if (!a.connected) return "Sin conexión con los agentes";
  const n = a.agents.filter((x) => x.status !== "down").length;
  return `Listo · ${n} ${n === 1 ? "agente conectado" : "agentes conectados"}`;
}

/** 'Pensando con N agentes…' while a turn runs. */
function thinkingLine(a: AgentsStatusResponse | null): string {
  const n = a?.connected ? a.agents.filter((x) => x.status !== "down").length : 0;
  return n === 0 ? "Pensando…" : `Pensando con ${n} ${n === 1 ? "agente" : "agentes"}…`;
}

/** Fetches the backend analysis of the issue once and hands it to the card. */
function AnalysisLoader({ caseId, item, mode, open, busy, onApprove, onReject }: { caseId: string; item: DecisionItem; mode: AnalysisRef["mode"]; open: boolean; busy: boolean; onApprove: (i: DecisionItem) => void; onReject: (i: DecisionItem) => void }) {
  const api = useApi();
  const [analysis, setAnalysis] = useState<AnalysisState>({ status: "loading" });
  useEffect(() => {
    let alive = true;
    if (!item.issueId) {
      setAnalysis({ status: "soon" });
      return;
    }
    void fetchIssueAnalysis(api, caseId, item.issueId).then((a) => alive && setAnalysis(a));
    return () => {
      alive = false;
    };
  }, [api, caseId, item.issueId]);
  return <AnalysisCard item={item} analysis={analysis} mode={mode} open={open} busy={busy} onApprove={onApprove} onReject={onReject} extra={item.isTransfer ? <TransferOptions caseId={caseId} sku={item.sku} issueId={item.issueId} /> : undefined} />;
}

/** Agente window: the existing chat (useChat) in the copilot look, with the pinned context and the analysis cards. */
export default function AgentWindow({
  caseId,
  storeId = "",
  simToday = "",
  chat,
  items,
  openIds,
  busyId = null,
  agents = null,
  pendingLine,
  onApprove,
  onReject,
}: {
  caseId: string;
  storeId?: string;
  simToday?: string;
  chat: Chat;
  /** Every decision seen this session, so a decided card still renders as 'Decisión registrada'. */
  items: DecisionItem[];
  /** Ids still pending (default: all). */
  openIds?: string[];
  /** Card with a decision request in flight. */
  busyId?: string | null;
  /** GET /agents/status; null while unknown or when the route is missing. */
  agents?: AgentsStatusResponse | null;
  pendingLine: string;
  onApprove: (item: DecisionItem) => void;
  onReject: (item: DecisionItem) => void;
}) {
  const { state, dispatch, showToast } = useCopilot();
  const [draft, setDraft] = useState("");
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => setDraft(""), [caseId]);
  const busy = chat.status === "working";
  const pendingIds = new Set(openIds ?? items.map((i) => i.id));

  const count = chat.messages.length + state.analyses.length;
  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [count, chat.status]);

  const send = (text: string) => {
    const clean = text.trim();
    if (!clean || busy) return;
    const ctx = state.ctx;
    void chat.send(clean, ctx?.issueId ? { context: { issue_id: ctx.issueId, ...(ctx.optionId ? { option_id: ctx.optionId } : {}), mode: "dialogo" } } : undefined);
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    send(draft);
    setDraft("");
  };

  const cardsAt = (at: number): AnalysisRef[] => state.analyses.filter((a) => Math.min(a.at, chat.messages.length) === at);
  const renderCards = (at: number) =>
    cardsAt(at).map((a) => {
      const item = items.find((i) => i.id === a.itemId);
      if (!item) return null;
      return <AnalysisLoader key={a.id} caseId={caseId} item={item} mode={a.mode} open={pendingIds.has(item.id)} busy={busyId === item.id} onApprove={onApprove} onReject={onReject} />;
    });

  return (
    <>
      <div ref={scroller} className="fixed inset-x-0 bottom-[204px] top-[100px] overflow-y-auto">
        <div className="mx-auto max-w-[640px] px-4 pb-4">
          <section className="flex flex-col items-center px-2 pb-4 pt-5 text-center">
            <AgentOrb size={116} />
            <span className="mt-2 font-label-sm text-label-sm text-on-surface-variant">{busy ? thinkingLine(agents) : agentsLine(agents)}</span>
            <h1 className="m-0 mt-2 font-headline-lg text-headline-lg tracking-tight text-primary">¿Qué decidimos hoy?</h1>
            <p className="m-0 mt-1 font-body-md text-body-md text-on-surface-variant">{pendingLine}</p>
          </section>

          <ConversationBar storeId={storeId} simToday={simToday} caseId={caseId} />

          {state.ctx && (
            <div className="mb-3 flex items-center gap-2 rounded-full bg-surface-container-high py-2 pl-3.5 pr-2 text-primary">
              <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-secondary">push_pin</span>
              <span className="min-w-0 flex-1 truncate font-label-md text-label-md normal-case tracking-normal">Hablando de: {state.ctx.title}</span>
              <button type="button" onClick={() => dispatch({ type: "ctx", ctx: null })} aria-label="Quitar contexto" className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full p-0 text-on-surface-variant">
                <span aria-hidden="true" className="flex h-8 w-8 items-center justify-center rounded-full bg-white/70">
                  <span className="material-symbols-outlined text-[16px]">close</span>
                </span>
              </button>
            </div>
          )}

          <div className="flex flex-col gap-2.5">
            {chat.historyLoading && chat.messages.length === 0 && <ChatSkeleton />}
            {chat.messages.map((m, i) => (
              <div key={m.id} className="contents">
                {renderCards(i)}
                {m.role === "user" && <UserBubble m={m} />}
                {m.role === "assistant" && <AssistantBubble m={m} />}
                {m.role === "error" && (
                  <div role="alert" className="max-w-[90%] rounded-[14px] bg-error-container px-4 py-2.5 text-on-error-container">
                    <p className="m-0 font-body-md text-body-md">{m.text}</p>
                    <button type="button" onClick={() => void chat.retry(m.retryText)} className="mt-1 min-h-[44px] underline font-label-sm text-label-sm">Reintentar</button>
                  </div>
                )}
              </div>
            ))}
            {renderCards(chat.messages.length)}
            {busy && (
              <div className="flex items-center gap-2">
                <AgentOrb size={28} />
                <span role="status" className="rounded-full border border-surface-container-high bg-white px-3.5 py-2 font-label-md text-label-md normal-case tracking-normal text-on-surface-variant">
                  {consultingText(chat.progress) ?? (chat.stillRunning ? "El copiloto sigue trabajando…" : "Esperando respuesta…")}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="fixed inset-x-4 bottom-[92px] z-30 mx-auto flex max-w-[608px] flex-col gap-2">
        <div className="flex gap-2 overflow-x-auto">
          {COPILOT_SUGGESTIONS.map((c) => (
            <button key={c} type="button" onClick={() => send(c)} className="min-h-[44px] flex-shrink-0 rounded-full bg-surface-container px-3.5 py-2 text-[13px] leading-[18px] text-secondary">{c}</button>
          ))}
        </div>
        <form onSubmit={submit} className="m-0 flex items-center gap-2 rounded-full border border-surface-container-high bg-white p-1.5 shadow-card">
          <button type="button" onClick={() => showToast("Voz: disponible pronto")} aria-label="Hablar con el copiloto" className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full bg-surface-container p-0 text-secondary">
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">mic</span>
          </button>
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Pregunta o decide algo…"
            aria-label="Mensaje para el copiloto"
            className="min-w-0 flex-1 bg-transparent p-0 font-body-md text-body-md text-on-surface outline-none"
          />
          <button type="submit" disabled={!draft.trim() || busy} aria-label="Enviar mensaje" className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full bg-secondary p-0 text-white shadow-[0_4px_6px_-1px_rgba(122,86,73,.2)] disabled:opacity-40">
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">send</span>
          </button>
        </form>
      </div>
    </>
  );
}
