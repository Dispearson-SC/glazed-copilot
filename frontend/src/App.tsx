import { Navigate, Route, Routes } from "react-router-dom";
import AlertsPage from "./pages/AlertsPage";
import ChatPage from "./pages/ChatPage";
import CasesPage from "./pages/CasesPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import BottomNav from "./shell/BottomNav";
import TopBar from "./shell/TopBar";
import InventoryPage from "./pages/InventoryPage";
import WeekPage from "./pages/WeekPage";
import DecisionsPage from "./pages/DecisionsPage";
import PurchasesPage from "./pages/PurchasesPage";
import SimControl from "./SimControl";
import { useSession } from "./SessionContext";
import TracePage from "./pages/TracePage";
import { useStores } from "./components";

function StoreRedirect({ to }: { to: "trace" | "purchases" | "decisions" | "inventory" | "week" }) {
  const { storeId } = useStores();
  const session = useSession();
  const id = session.storeId || storeId;
  return id ? <Navigate to={`/stores/${id}/${to}`} replace /> : <p className="muted">Cargando sucursales…</p>;
}

export default function App() {
  return (
    <div className="app min-h-screen bg-surface text-on-surface">
      <TopBar />
      <main className="pt-20 pb-24 px-margin max-w-3xl mx-auto flex flex-col gap-space-md">
        <div className="bg-surface-container rounded-[16px] px-space-md py-space-sm text-body-md">
          <SimControl />
        </div>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/purchases" element={<StoreRedirect to="purchases" />} />
          <Route path="/stores/:storeId/purchases" element={<PurchasesPage />} />
          <Route path="/decisions" element={<StoreRedirect to="decisions" />} />
          <Route path="/stores/:storeId/decisions" element={<DecisionsPage />} />
          <Route path="/inventory" element={<StoreRedirect to="inventory" />} />
          <Route path="/stores/:storeId/inventory" element={<InventoryPage />} />
          <Route path="/week" element={<StoreRedirect to="week" />} />
          <Route path="/stores/:storeId/week" element={<WeekPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/trace" element={<StoreRedirect to="trace" />} />
          <Route path="/stores/:storeId/trace" element={<TracePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<p>Página no encontrada</p>} />
        </Routes>
      </main>
      <BottomNav />
    </div>
  );
}
