import { useState } from "react";
import { Link } from "react-router-dom";
import { useChat } from "../useChat";
import ChatView from "./ChatView";

export default function FloatingChat({ storeId, caseId, storeName, simToday }: {
  storeId: string; caseId: string; storeName?: string; simToday?: string;
}) {
  const [open, setOpen] = useState(false);
  const chat = useChat(caseId, { storeId, enabled: open });
  if (!caseId) return null;
  return (
    <>
      {open && (
        <section
          role="region"
          aria-label="Chat flotante del turno"
          className="fixed z-50 left-4 right-4 bottom-40 sm:left-auto sm:w-[380px] rounded-[20px] overflow-hidden bg-surface-container-lowest border border-surface-container shadow-xl shadow-primary-container/20 flex flex-col max-h-[60vh]"
        >
          <div className="bg-primary-container text-surface-container-lowest px-space-md py-3 flex items-center gap-space-sm flex-shrink-0">
            <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-tertiary-fixed-dim">smart_toy</span>
            <div className="flex-1 min-w-0 flex flex-col">
              <span className="font-headline-sm text-headline-sm tracking-tight leading-none">Chat del turno</span>
              <span className="font-label-sm text-label-sm text-surface-variant font-normal truncate">
                {storeName ?? ""}{simToday ? ` · ${simToday}` : ""}
              </span>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Cerrar chat"
              className="w-9 h-9 flex items-center justify-center rounded-full bg-surface-container-lowest/10">
              <span aria-hidden="true" className="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>
          <div className="flex flex-col gap-space-xs overflow-y-auto p-space-sm">
            <ChatView chat={chat} compact traceBase={`/stores/${storeId}/trace?case=${caseId}`} />
            <Link to="/chat" className="flex items-center justify-center gap-1 font-label-sm text-label-sm text-secondary">
              <span aria-hidden="true" className="material-symbols-outlined text-[14px]">open_in_full</span>
              Abrir chat completo
            </Link>
          </div>
        </section>
      )}
      <button type="button" onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Cerrar chat del turno" : "Abrir chat del turno"} aria-expanded={open}
        className="fixed z-50 bottom-20 right-4 w-14 h-14 rounded-full bg-primary-container text-surface-container-lowest flex items-center justify-center shadow-xl shadow-primary-container/30 hover:bg-primary transition-colors">
        <span aria-hidden="true" className="material-symbols-outlined text-[24px]">{open ? "close" : "chat"}</span>
      </button>
    </>
  );
}
