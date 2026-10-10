import ChatView from "../chat/ChatView";
import PageShell from "../components/PageShell";
import { useStores } from "../components";
import { useSession } from "../SessionContext";
import { useChat } from "../useChat";
import { useCurrentCase } from "../useCurrentCase";
import { useAgents } from "../useInbox";

/** "Sin agente" or "N agentes" (Chat.dc.html badge). */
const badge = (n: number): string => (n === 0 ? "Sin agente" : `${n} ${n === 1 ? "agente" : "agentes"}`);

export default function ChatPage() {
  const session = useSession();
  const { storeId: firstId } = useStores();
  const storeId = session.storeId || firstId;
  const { currentCase, loading } = useCurrentCase(storeId, session.refreshKey);
  const caseId = currentCase?.case_id ?? "";
  const chat = useChat(caseId, { storeId });
  const agents = useAgents();
  const connected = agents?.connected ? agents.agents.filter((a) => a.status !== "down").length : 0;

  return (
    <PageShell columnClass="flex flex-col w-full max-w-[640px] mx-auto gap-space-md pt-space-xs">
      <section
        data-testid="chat-header"
        className="relative overflow-hidden rounded-[20px] bg-primary-container text-surface-container-lowest p-space-lg shadow-xl shadow-primary-container/20"
      >
        <div aria-hidden="true" className="absolute -right-12 -top-12 w-48 h-48 rounded-full bg-secondary-container/10 blur-2xl pointer-events-none"></div>
        <div aria-hidden="true" className="absolute -left-12 -bottom-12 w-40 h-40 rounded-full bg-on-tertiary-container/10 blur-2xl pointer-events-none"></div>
        <div className="relative z-10 flex items-center justify-between gap-2">
          <div className="flex items-center gap-space-sm min-w-0">
            <div className="w-9 h-9 rounded-full bg-surface-container-lowest/10 flex items-center justify-center text-tertiary-fixed-dim flex-shrink-0">
              <span aria-hidden="true" className="material-symbols-outlined text-[20px]">smart_toy</span>
            </div>
            <div className="flex flex-col min-w-0">
              <h1 className="font-headline-sm text-headline-sm tracking-tight">Chat del turno</h1>
              <p className="font-label-sm text-label-sm text-surface-variant font-normal truncate">Conversa con el asistente de barra</p>
            </div>
          </div>
          <span
            data-testid="chat-status"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container-lowest/10 font-label-sm text-label-sm whitespace-nowrap"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-tertiary-fixed-dim"></span>
            {badge(connected)}
          </span>
        </div>
      </section>
      {!currentCase ? (
        <p className="text-on-surface-variant font-body-md text-body-md">{loading ? "Cargando caso…" : "Sin caso activo para esta sucursal"}</p>
      ) : (
        <ChatView chat={chat} />
      )}
      <p className="text-center font-label-sm text-label-sm text-on-surface-variant">
        {connected === 0 ? "Interfaz lista. Conecta un agente para recibir respuestas." : `Interfaz lista. ${connected} ${connected === 1 ? "agente conectado" : "agentes conectados"}.`}
      </p>
    </PageShell>
  );
}
