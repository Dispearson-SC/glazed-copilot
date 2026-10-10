import { useEffect, useState } from "react";
import { dateLabel } from "../../format";
import { useConversations } from "../../useConversations";

const pill =
  "inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-full border border-partition/60 bg-white px-4 font-label-md text-label-md font-semibold normal-case tracking-normal text-secondary shadow-card disabled:opacity-40";

/** Agente window: start a new conversation or reopen an earlier one (a conversation is a case of the same store and sim date). */
export default function ConversationBar({ storeId, simToday, caseId }: { storeId: string; simToday: string; caseId: string }) {
  const [open, setOpen] = useState(false);
  const { conversations, previews, busy, error, startNew, select } = useConversations(storeId, simToday, caseId, open);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  if (!caseId) return null;
  return (
    <>
      <div className="mb-3 flex flex-wrap justify-center gap-2">
        <button type="button" disabled={busy} onClick={() => void startNew()} className={pill}>
          <span aria-hidden="true" className="material-symbols-outlined text-[18px]">add_comment</span>
          Nueva conversación
        </button>
        <button type="button" aria-haspopup="dialog" onClick={() => setOpen(true)} className={pill}>
          <span aria-hidden="true" className="material-symbols-outlined text-[18px]">history</span>
          Conversaciones anteriores
        </button>
      </div>
      {error && <p role="alert" className="m-0 mb-3 text-center font-label-sm text-label-sm text-on-error-container">{error}</p>}
      {open && (
        <div className="fixed inset-0 z-[60]">
          <div data-testid="conversations-backdrop" className="absolute inset-0 bg-black/30" onClick={() => setOpen(false)} />
          <div role="dialog" aria-label="Conversaciones anteriores" className="absolute inset-x-0 bottom-0 mx-auto flex max-h-[75vh] max-w-[640px] flex-col rounded-t-[24px] border border-partition/60 bg-elevation p-4 shadow-card">
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
        </div>
      )}
    </>
  );
}
