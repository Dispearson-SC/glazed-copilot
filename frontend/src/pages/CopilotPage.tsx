import { useCallback, useRef } from "react";
import AgentWindow from "../components/copilot/AgentWindow";
import AlertsWindow from "../components/copilot/AlertsWindow";
import BranchWindow from "../components/copilot/BranchWindow";
import CapsuleNav, { type CapsuleBadges } from "../components/copilot/CapsuleNav";
import CopilotTopBar from "../components/copilot/CopilotTopBar";
import DecisionsWindow from "../components/copilot/DecisionsWindow";
import MemoriesWindow from "../components/copilot/MemoriesWindow";
import RejectSheet from "../components/copilot/RejectSheet";
import Toast from "../components/copilot/Toast";
import { isUnavailable } from "../api";
import { useStores } from "../components";
import { buildDayView, buildInventoryRows, buildMemories, buildScheduled, buildWarnings, type DecisionItem, type WarningItem } from "../data/copilot";
import { splitStoreName } from "../format";
import { CopilotProvider, useCopilot } from "../state/copilotStore";
import { useSession } from "../SessionContext";
import { storeLabel } from "../types";
import { useChat } from "../useChat";
import { useBranchData } from "../useBranchData";
import { useMemoryData, useWarningsData } from "../useMemoryData";
import { useCopilotData } from "../useCopilotData";
import { useCurrentCase } from "../useCurrentCase";
import { useDecide } from "../useDecide";

function CopilotShell() {
  const { state, dispatch, showToast } = useCopilot();
  const { stores, storeId: firstId } = useStores();
  const session = useSession();
  const storeId = session.storeId || firstId;
  const active = stores.find((s) => s.store_id === storeId);
  const { currentCase } = useCurrentCase(storeId, session.refreshKey);
  const caseId = currentCase?.case_id ?? "";
  const simToday = currentCase?.sim_today ?? "";
  const chat = useChat(caseId, { storeId });
  const data = useCopilotData(caseId, simToday, session.refreshKey);
  const branch_ = useBranchData(caseId, simToday, state.tab === "sucursal", session.refreshKey);
  const warningsData = useWarningsData(storeId, caseId, session.refreshKey);
  const memoryData = useMemoryData(caseId, state.tab === "memorias", session.refreshKey);
  const { decide, busyId } = useDecide(caseId, data.refresh);
  const [site, branch] = splitStoreName(active ? storeLabel(active) : "Sucursal");

  // Every decision seen this session stays available to the chat cards even after it is decided.
  const known = useRef(new Map<string, DecisionItem>());
  data.items.forEach((i) => known.current.set(i.id, i));
  const visible = data.items.filter((i) => !state.handled.includes(i.id));
  const approvals = visible.filter((i) => i.kind === "approval").length;
  const techs = visible.length - approvals;
  const pendingLine = `${approvals} esperan tu opinión · ${techs} listas para aceptar`;
  const warnings = warningsData ? buildWarnings(warningsData) : [];
  const badges: CapsuleBadges = { decisiones: visible.length, memorias: state.learned.length, alertas: warnings.length };

  const openCard = useCallback(
    (item: DecisionItem, mode: "analizar" | "dialogo") => {
      dispatch({ type: "analysis", itemId: item.id, title: item.title, mode, at: chat.messages.length + 1, issueId: item.issueId, optionId: item.optionId });
      const userText = mode === "analizar" ? `Analiza: ${item.title}` : `Quiero dialogar sobre: ${item.title}`;
      void chat.send(userText, { context: { issue_id: item.issueId, ...(item.optionId ? { option_id: item.optionId } : {}), mode } });
    },
    [chat, dispatch],
  );

  const b = branch_.data;
  const dayView = b ? buildDayView(state.day, { asOf: simToday, forecast: b.forecast, ayer: b.ayer, hoy: b.hoy, kpis: b.kpis, expiring: b.expiring, outlook: b.outlook }) : null;

  const ask = (w: WarningItem) => {
    const userText = `Explícame: ${w.title}`;
    dispatch({ type: "ctx", ctx: { id: w.id, title: w.title } });
    dispatch({ type: "tab", tab: "agente" });
    void chat.send(userText);
  };

  const reject = state.rejectFor ? known.current.get(state.rejectFor) : undefined;

  return (
    <div className="min-h-screen bg-surface font-body-md text-body-md text-on-surface">
      <CopilotTopBar branch={branch ?? site} onSettings={() => showToast("Ajustes: disponible pronto")} />
      {state.tab === "agente" && (
        <AgentWindow
          caseId={caseId}
          chat={chat}
          items={[...known.current.values()]}
          openIds={visible.map((i) => i.id)}
          busyId={busyId}
          pendingLine={data.items.length || !data.loading ? pendingLine : ""}
          onApprove={(i) => void decide(i, true)}
          onReject={(i) => dispatch({ type: "openReject", id: i.id })}
        />
      )}
      {state.tab === "decisiones" && (
        <DecisionsWindow
          items={visible}
          simToday={simToday}
          loadState={data.items.length === 0 && data.error ? (isUnavailable(data.error) ? "soon" : "error") : "ok"}
          menuFor={state.menuFor}
          busyId={busyId}
          accepted={state.accepted}
          onAnalyze={(i) => openCard(i, "analizar")}
          onAccept={(i) => void decide(i, true)}
          onReject={(i) => dispatch({ type: "openReject", id: i.id })}
          onToggleMenu={(i) => dispatch({ type: "toggleMenu", id: i.id })}
          onDialog={(i) => openCard(i, "dialogo")}
        />
      )}
      {state.tab === "sucursal" && (
        <BranchWindow
          day={state.day}
          onDay={(day) => dispatch({ type: "day", day })}
          view={dayView}
          inventory={buildInventoryRows(b?.inventory ?? null, b?.plan ?? null)}
          inventoryFailed={Boolean(b?.failed.includes("inventory"))}
          scheduled={buildScheduled(b?.deliveries ?? null)}
          pendingBuy={visible.filter((i) => i.kind === "tech").length}
          partial={Boolean(b?.failed.length)}
          onGoDecisiones={() => dispatch({ type: "tab", tab: "decisiones" })}
        />
      )}
      {state.tab === "memorias" && (
        <MemoriesWindow
          memories={buildMemories({ history: memoryData.data?.history ?? null, suppliers: memoryData.data?.suppliers ?? null, learned: state.learned })}
          filter={state.memFilter}
          onFilter={(value) => dispatch({ type: "memFilter", value })}
          loading={memoryData.loading}
        />
      )}
      {state.tab === "alertas" && <AlertsWindow warnings={warnings} filter={state.alertFilter} onFilter={(value) => dispatch({ type: "alertFilter", value })} onAsk={ask} />}
      <CapsuleNav tab={state.tab} onChange={(tab) => dispatch({ type: "tab", tab })} badges={badges} />
      <Toast text={state.toast} />
      {reject && (
        <RejectSheet
          title={reject.title}
          busy={busyId === reject.id}
          onCancel={() => dispatch({ type: "closeReject" })}
          onSubmit={async (r) => {
            if (await decide(reject, false, r)) dispatch({ type: "closeReject" });
          }}
        />
      )}
    </div>
  );
}

/** /copiloto: the decision copilot with its five windows and the capsule navigation. */
export default function CopilotPage() {
  return (
    <CopilotProvider>
      <CopilotShell />
    </CopilotProvider>
  );
}
