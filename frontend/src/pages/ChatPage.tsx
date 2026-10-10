import ChatView from "../chat/ChatView";
import { useStores } from "../components";
import { useSession } from "../SessionContext";
import { useChat } from "../useChat";
import { useCurrentCase } from "../useCurrentCase";

export default function ChatPage() {
  const session = useSession();
  const { stores, storeId: firstId } = useStores();
  const storeId = session.storeId || firstId;
  const { currentCase, loading } = useCurrentCase(storeId, session.refreshKey);
  const caseId = currentCase?.case_id ?? "";
  const chat = useChat(caseId, { storeId });
  const store = stores.find((s) => s.store_id === storeId);

  return (
    <section className="flex flex-col gap-space-md">
      <div data-testid="chat-header" className="relative overflow-hidden rounded-[20px] bg-primary-container text-surface-container-lowest p-space-lg shadow-xl shadow-primary-container/20">
        <div className="flex items-center gap-space-sm">
          <div className="w-9 h-9 rounded-full bg-surface-container-lowest/10 flex items-center justify-center text-tertiary-fixed-dim">
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">smart_toy</span>
          </div>
          <div className="flex flex-col min-w-0">
            <h2 className="font-headline-sm text-headline-sm tracking-tight">Chat con el copiloto</h2>
            <p className="font-label-sm text-label-sm text-surface-variant font-normal truncate">
              {store?.display_name ?? "Sin sucursal"}
              {currentCase ? ` · ${currentCase.sim_today}` : ""}
            </p>
          </div>
        </div>
      </div>
      {!currentCase ? (
        <p className="text-on-surface-variant font-body-md text-body-md">{loading ? "Cargando caso…" : "Sin caso activo para esta sucursal"}</p>
      ) : (
        <ChatView chat={chat} />
      )}
    </section>
  );
}
