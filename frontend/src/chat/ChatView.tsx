import { useEffect, useRef, useState, type FormEvent } from "react";
import type { ChatMessage } from "../chatHistory";
import type { Proposal } from "../types";
import type { useChat } from "../useChat";

export const SUGGESTIONS = [
  "¿Qué tengo que pedir hoy?",
  "¿Cómo me fue ayer vs lo normal?",
  "¿Qué se me va a echar a perder esta semana?",
  "¿Qué alertas son urgentes?",
  "¿Qué pasó con las ventas esta semana?",
];

type Chat = ReturnType<typeof useChat>;

function MetaChip({ meta }: { meta: NonNullable<ChatMessage["meta"]> }) {
  const secs = (meta.elapsed_ms / 1000).toFixed(1);
  return (
    <div className="flex items-center gap-1.5 mt-1 font-label-sm text-label-sm text-on-surface-variant">
      {meta.source === "fast" && (
        <span className="px-2 py-0.5 rounded-full bg-tertiary-fixed text-on-tertiary-fixed-variant">Respuesta rápida</span>
      )}
      <span>{secs} s</span>
    </div>
  );
}

function Bubble({ m, onRetry }: { m: ChatMessage; onRetry: () => void }) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-[16px] rounded-br-[6px] bg-secondary text-surface-container-lowest px-4 py-2.5">
          <p className="font-body-md text-body-md whitespace-pre-wrap">{m.text}</p>
          {m.truncated && <p className="font-label-sm text-label-sm opacity-70">…(recortado)</p>}
        </div>
      </div>
    );
  }
  if (m.role === "error") {
    return (
      <div role="alert" className="max-w-[90%] rounded-[16px] bg-error-container text-on-error-container px-4 py-2.5">
        <p className="font-body-md text-body-md">{m.text}</p>
        <button type="button" onClick={onRetry} className="mt-1 underline font-label-sm text-label-sm">Reintentar</button>
      </div>
    );
  }
  return (
    <div className="flex justify-start gap-2">
      <div className="w-7 h-7 rounded-full bg-surface-container flex items-center justify-center text-secondary flex-shrink-0 mt-1">
        <span aria-hidden="true" className="material-symbols-outlined text-[16px]">smart_toy</span>
      </div>
      <div className="max-w-[85%] rounded-[16px] rounded-bl-[6px] bg-surface border border-surface-container px-4 py-2.5">
        <p className="font-body-md text-body-md text-on-surface whitespace-pre-wrap">{m.text}</p>
        {m.truncated && (
          <p className="font-label-sm text-label-sm text-on-surface-variant">…(recortado)</p>
        )}
        {m.steps && m.steps.length > 0 && (
          <details className="mt-1 font-label-sm text-label-sm text-on-surface-variant">
            <summary className="cursor-pointer">Pasos intermedios ({m.steps.length})</summary>
            <ul className="list-disc pl-4">
              {m.steps.map((t, i) => <li key={i}>{t}</li>)}
            </ul>
          </details>
        )}
        {m.meta && <MetaChip meta={m.meta} />}
      </div>
    </div>
  );
}

function ProposalCard({ p, onDecide }: { p: Proposal; onDecide: Chat["decide"] }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  async function go(approved: boolean) {
    setBusy(true);
    try {
      await onDecide(p.proposal_id, approved, approved ? undefined : reason.trim());
    } finally {
      setBusy(false);
    }
  }
  return (
    <div data-testid={`proposal-${p.proposal_id}`} className="rounded-[16px] border border-secondary-container bg-surface-container-low px-4 py-3 flex flex-col gap-space-xs">
      <p className="font-label-sm text-label-sm text-on-surface-variant">Propuesta pendiente · {p.action_type} · {p.tier}</p>
      <p className="font-body-md text-body-md text-on-surface">{p.rationale}</p>
      {rejecting ? (
        <div className="flex flex-col gap-space-xs">
          <label className="font-label-sm text-label-sm">
            Motivo del rechazo
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mt-1 w-full rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2"
            />
          </label>
          <div className="flex gap-2">
            <button type="button" disabled={busy || !reason.trim()} onClick={() => void go(false)}
              className="px-4 py-2 rounded-full bg-error text-on-error disabled:opacity-40">Confirmar rechazo</button>
            <button type="button" onClick={() => setRejecting(false)} className="px-4 py-2 rounded-full text-secondary">Cancelar</button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2">
          <button type="button" disabled={busy} onClick={() => void go(true)}
            className="px-4 py-2 rounded-full bg-secondary text-on-secondary disabled:opacity-40">Aprobar</button>
          <button type="button" disabled={busy} onClick={() => setRejecting(true)}
            className="px-4 py-2 rounded-full bg-surface-container text-secondary disabled:opacity-40">Rechazar</button>
        </div>
      )}
    </div>
  );
}

/** Conversation, suggestions and composer shared by the full page and the floating panel. */
export default function ChatView({ chat, compact = false }: { chat: Chat; compact?: boolean }) {
  const [draft, setDraft] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const busy = chat.status === "working";
  const count = chat.messages.length + chat.proposals.length;
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [count, chat.status]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    void chat.send(text);
  }

  return (
    <>
      <section
        aria-label="Conversación"
        className={`flex flex-col gap-space-sm ${compact ? "p-space-md overflow-y-auto" : "bg-surface-container-lowest rounded-[18px] p-space-md shadow-sm shadow-primary/5 border border-surface-container min-h-[320px]"}`}
      >
        {chat.messages.map((m) => (
          <Bubble key={m.id} m={m} onRetry={() => void chat.retry(m.retryText)} />
        ))}
        {chat.proposals.map((p) => <ProposalCard key={p.proposal_id} p={p} onDecide={chat.decide} />)}
        {chat.decisionError && <div role="alert" className="rounded-[14px] bg-error-container text-on-error-container px-4 py-2.5 font-body-md text-body-md">{chat.decisionError.message}</div>}
        {busy && (
          <p role="status" className="font-label-sm text-label-sm text-on-surface-variant">
            {chat.stillRunning ? "El copiloto sigue trabajando…" : "Esperando respuesta…"}
          </p>
        )}
        {chat.status === "waiting_approval" && chat.proposals.length === 0 && (
          <p className="font-label-sm text-label-sm text-on-surface-variant">Hay una acción esperando aprobación.</p>
        )}
        <div ref={bottom} />
      </section>
      {chat.messages.length === 0 && (
        <div className={`flex gap-2 overflow-x-auto pb-1 ${compact ? "px-space-md" : ""}`}>
          {(compact ? SUGGESTIONS.slice(0, 3) : SUGGESTIONS).map((chip) => (
            <button key={chip} type="button" onClick={() => setDraft(chip)}
              className="flex-shrink-0 px-3.5 py-2 rounded-full bg-surface-container text-secondary font-body-md text-body-md hover:bg-surface-variant transition-colors">
              {chip}
            </button>
          ))}
        </div>
      )}
      <form onSubmit={submit}
        className="flex items-center gap-2 rounded-full border border-surface-container bg-surface-container-lowest p-2 pl-4 shadow-sm shadow-primary/5 focus-within:border-secondary">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Escribe un mensaje…"
          aria-label="Escribe un mensaje"
          className="flex-1 min-w-0 bg-transparent outline-none font-body-md text-body-md text-on-surface placeholder:text-on-surface-variant/60"
        />
        <button type="submit" disabled={!draft.trim() || busy} aria-label="Enviar mensaje"
          className="w-11 h-11 rounded-full bg-secondary text-surface-container-lowest flex items-center justify-center shadow-md shadow-secondary/20 hover:bg-primary transition-all disabled:opacity-40">
          <span aria-hidden="true" className="material-symbols-outlined text-[20px]">send</span>
        </button>
      </form>
    </>
  );
}
