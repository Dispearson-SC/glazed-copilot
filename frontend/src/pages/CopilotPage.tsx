import CapsuleNav from "../components/copilot/CapsuleNav";
import CopilotTopBar from "../components/copilot/CopilotTopBar";
import Toast from "../components/copilot/Toast";
import { useStores } from "../components";
import { splitStoreName } from "../format";
import { CopilotProvider, useCopilot } from "../state/copilotStore";
import { useSession } from "../SessionContext";
import { storeLabel } from "../types";

function CopilotShell() {
  const { state, dispatch, showToast } = useCopilot();
  const { stores, storeId: firstId } = useStores();
  const session = useSession();
  const active = stores.find((s) => s.store_id === (session.storeId || firstId));
  const [site, branch] = splitStoreName(active ? storeLabel(active) : "Sucursal");

  return (
    <div className="min-h-screen bg-surface font-body-md text-body-md text-on-surface">
      <CopilotTopBar branch={branch ?? site} onSettings={() => showToast("Ajustes: disponible pronto")} />
      <main className="mx-auto w-full max-w-[640px] px-4 pb-28 pt-16" data-window={state.tab} />
      <CapsuleNav tab={state.tab} onChange={(tab) => dispatch({ type: "tab", tab })} badges={{}} />
      <Toast text={state.toast} />
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
