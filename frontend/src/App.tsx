import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import AlertsPage from "./pages/AlertsPage";
import CasesPage from "./pages/CasesPage";
import HomePage from "./pages/HomePage";
import PurchasesPage from "./pages/PurchasesPage";
import SimControl from "./SimControl";
import { useSession } from "./SessionContext";
import TracePage from "./pages/TracePage";
import { useStores } from "./components";

function StoreRedirect({ to }: { to: "trace" | "purchases" }) {
  const { storeId } = useStores();
  const session = useSession();
  const id = session.storeId || storeId;
  return id ? <Navigate to={`/stores/${id}/${to}`} replace /> : <p className="muted">Cargando sucursales…</p>;
}

export default function App() {
  return (
    <div className="app">
      <header>
        <h1>Glazed Copilot</h1>
        <nav>
          <NavLink to="/" end>Inicio</NavLink>
          <NavLink to="/purchases">Compras</NavLink>
          <NavLink to="/alerts">Alertas</NavLink>
          <NavLink to="/cases">Casos</NavLink>
          <NavLink to="/trace">Inspector</NavLink>
        </nav>
        <SimControl />
      </header>
      <main>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/purchases" element={<StoreRedirect to="purchases" />} />
          <Route path="/stores/:storeId/purchases" element={<PurchasesPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/trace" element={<StoreRedirect to="trace" />} />
          <Route path="/stores/:storeId/trace" element={<TracePage />} />
          <Route path="*" element={<p>Página no encontrada</p>} />
        </Routes>
      </main>
    </div>
  );
}
