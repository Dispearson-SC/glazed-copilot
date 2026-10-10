import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { dateLabel } from "../../format";
import { useSession } from "../../SessionContext";
import { useCopilot } from "../../state/copilotStore";
import { useConversations } from "../../useConversations";
import { useCurrentCase } from "../../useCurrentCase";

const pill =
  "-mt-2 flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full border border-partition/60 bg-white p-0 text-secondary shadow-card disabled:opacity-40";

/** Fixed top row: new conversation (left), the day switcher (children, centre) and earlier conversations (right). Both actions switch to the Agente tab first. */
export default function ConversationBar({ storeId, children, className = "" }: { storeId: string; children: ReactNode; className?: string }) {
  const session = useSession();
  const { dispatch } = useCopilot();
  const { currentCase } = useCurrentCase(storeId, session.refreshKey);
  const caseId = currentCase?.case_id ?? "";
  const simToday = currentCase?.sim_today ?? "";
  const [open, setOpen] = useState(false);
  const { conversations, previews, busy, error, startNew, select } = useConversations(storeId, simToday, caseId, open);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <div className={`mx-auto flex max-w-[640px] items-start justify-center gap-2 px-4 ${className}`}>
        <button
          type="button"
          aria-label="Nueva conversación"
          disabled={busy || !caseId}
          onClick={() => {
            dispatch({ type: "tab", tab: "agente" });
            void startNew();
          }}
          className={pill}
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[22px]">add_comment</span>
        </button>
        {children}
        <button
          type="button"
          aria-label="Conversaciones anteriores"
          aria-haspopup="dialog"
          disabled={!caseId}
          onClick={() => {
            dispatch({ type: "tab", tab: "agente" });
            setOpen(true);
          }}
          className={pill}
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[22px]">history</span>
        </button>
      </div>
      {error && <p role="alert" className="m-0 text-center font-label-sm text-label-sm text-on-error-container">{error}</p>}
      {/* Portal to <body>: the top bar uses backdrop-blur, which makes `fixed` children position against the bar instead of the viewport. */}
      {open && createPortal(
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <div data-testid="conversations-backdrop" className="absolute inset-0 bg-primary-container/40" onClick={() => setOpen(false)} />
          <div role="dialog" aria-modal="true" aria-label="Conversaciones anteriores" className="relative flex max-h-[80dvh] w-full max-w-[480px] flex-col rounded-[24px] border border-partition/60 bg-elevation p-4 shadow-hero">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="m-0 font-headline-sm text-headline-sm text-primary" style={{ fontFamily: "Inter, 'Playfair Display', serif" }}>Conversaciones</h2>
              <button type="button" aria-label="Cerrar conversaciones" onClick={() => setOpen(false)} className="flex h-11 w-11 items-center justify-center rounded-full bg-transparent p-0 text-on-surface-variant">
                <span aria-hidden="true" className="material-symbols-outlined text-[22px]">close</span>
              </button>
            </div>
            <ul className="m-0 flex-1 list-none space-y-2 overflow-y-auto p-0">
              {conversations.length === 0 && <li className="px-1 py-3 font-body-md text-body-md text-on-surface-variant">Aún no hay conversaciones</li>}
              {conversations.map((c) => (
                <li key={c.case_id}>
                  <button
                    type="button"
                    data-case={c.case_id}
                    aria-label={`Abrir conversación ${c.title}`}
                    aria-current={c.case_id === caseId ? "true" : undefined}
                    onClick={() => {
                      select(c.case_id);
                      setOpen(false);
                    }}
                    className={`flex min-h-[44px] w-full flex-col gap-0.5 rounded-[14px] border px-3 py-2 text-left ${c.case_id === caseId ? "border-primary bg-white" : "border-partition/40 bg-transparent"}`}
                  >
                    <span className="truncate font-body-md text-body-md font-semibold text-primary">{c.title || "Conversación"}</span>
                    <span className="font-label-sm text-label-sm font-normal text-on-surface-variant">{dateLabel(c.sim_today)}</span>
                    <span className="line-clamp-2 font-label-sm text-label-sm font-normal text-on-surface-variant">{previews[c.case_id] || "Sin mensajes"}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
