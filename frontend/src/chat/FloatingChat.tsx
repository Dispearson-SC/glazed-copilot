import { useState } from "react";
import { Link } from "react-router-dom";
import { agentsLabel, useAgents } from "../useInbox";
import { useChat } from "../useChat";
import ChatView from "./ChatView";

export default function FloatingChat({ storeId, caseId }: {
  storeId: string; caseId: string; storeName?: string;
}) {
  const agents = useAgents();
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
          <div className="relative overflow-hidden bg-primary-container text-surface-container-lowest px-space-md py-3 flex items-center gap-space-sm flex-shrink-0">
            <div className="absolute -right-8 -top-8 w-28 h-28 rounded-full bg-secondary-container/10 blur-2xl pointer-events-none"></div>
            <div className="relative z-10 w-8 h-8 rounded-full bg-surface-container-lowest/10 flex items-center justify-center text-tertiary-fixed-dim flex-shrink-0">
              <span aria-hidden="true" className="material-symbols-outlined text-[18px]">smart_toy</span>
            </div>
            <div className="relative z-10 flex-1 min-w-0 flex flex-col">
              <span className="font-headline-sm text-headline-sm tracking-tight leading-none">Chat del turno</span>
              <span className="font-label-sm text-label-sm text-surface-variant font-normal truncate">
                {agentsLabel(agents)}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Cerrar chat"
              className="relative z-10 w-9 h-9 flex items-center justify-center rounded-full bg-surface-container-lowest/10"
            >
              <span aria-hidden="true" className="material-symbols-outlined text-[18px]">close</span>
            </button>
          </div>
          <ChatView
            chat={chat}
            compact
            footer={
              <Link to="/chat" className="mt-1.5 flex items-center justify-center gap-1 font-label-sm text-label-sm text-secondary">
                <span aria-hidden="true" className="material-symbols-outlined text-[14px]">open_in_full</span>
                Abrir chat completo
              </Link>
            }
          />
        </section>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Cerrar chat del turno" : "Abrir chat del turno"}
        aria-expanded={open}
        className="fixed z-50 bottom-20 right-4 w-14 h-14 rounded-full bg-primary-container text-surface-container-lowest flex items-center justify-center shadow-xl shadow-primary-container/30 hover:bg-primary transition-colors active:scale-[0.95]"
      >
        <span aria-hidden="true" className="material-symbols-outlined text-[24px]">{open ? "close" : "chat"}</span>
      </button>
    </>
  );
}
