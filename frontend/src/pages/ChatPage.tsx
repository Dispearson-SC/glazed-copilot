import ChatView from "../chat/ChatView";
import PageShell from "../components/PageShell";
import { useStores } from "../components";
import { useSession } from "../SessionContext";
import { useChat } from "../useChat";
import { useCurrentCase } from "../useCurrentCase";

const STATUS = { idle: "En línea", working: "Trabajando…", waiting_approval: "Esperando aprobación" } as const;

export default function ChatPage() {
  const session = useSession();
  const { stores, storeId: firstId } = useStores();
  const storeId = session.storeId || firstId;
  const { currentCase, loading } = useCurrentCase(storeId, session.refreshKey);
  const caseId = currentCase?.case_id ?? "";
  const chat = useChat(caseId, { storeId });
  const store = stores.find((s) => s.store_id === storeId);

  return (
    <PageShell subtitle="Chat" columnClass="flex flex-col w-full max-w-[640px] mx-auto gap-space-md pt-space-xs">
      <section
        data-testid="chat-header"
        className="relative overflow-hidden rounded-[20px] bg-primary-container text-surface-container-lowest p-space-lg shadow-xl shadow-primary-container/20"
      >
        <div className="absolute -right-12 -top-12 w-48 h-48 rounded-full bg-secondary-container/10 blur-2xl pointer-events-none"></div>
        <div className="absolute -left-12 -bottom-12 w-40 h-40 rounded-full bg-on-tertiary-container/10 blur-2xl pointer-events-none"></div>
        <div className="relative z-10 flex items-center justify-between gap-2">
          <div className="flex items-center gap-space-sm min-w-0">
            <div className="w-9 h-9 rounded-full bg-surface-container-lowest/10 flex items-center justify-center text-tertiary-fixed-dim flex-shrink-0">
              <span aria-hidden="true" className="material-symbols-outlined text-[20px]">smart_toy</span>
            </div>
            <div className="flex flex-col min-w-0">
              <h1 className="font-headline-sm text-headline-sm tracking-tight">Chat del turno</h1>
              <p className="font-label-sm text-label-sm text-surface-variant font-normal truncate">
                {store?.display_name ?? "Sin sucursal"}
                {currentCase ? ` · ${currentCase.sim_today}` : ""}
              </p>
            </div>
          </div>
          <span
            data-testid="chat-status"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container-lowest/10 font-label-sm text-label-sm whitespace-nowrap"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-tertiary-fixed-dim"></span>
            {STATUS[chat.status]}
          </span>
        </div>
      </section>
      {!currentCase ? (
        <p className="text-on-surface-variant font-body-md text-body-md">{loading ? "Cargando caso…" : "Sin caso activo para esta sucursal"}</p>
      ) : (
        <ChatView chat={chat} />
      )}
      <p className="text-center font-label-sm text-label-sm text-on-surface-variant">
        Las propuestas pendientes aparecen en la conversación para aprobar o rechazar.
      </p>
    </PageShell>
  );
}
