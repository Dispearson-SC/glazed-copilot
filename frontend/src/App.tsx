import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import AlertsPage from "./pages/AlertsPage";
import CasesPage from "./pages/CasesPage";
import TracePage from "./pages/TracePage";
import { useStores } from "./components";

function TraceRedirect() {
  const { storeId } = useStores();
  return storeId ? <Navigate to={`/stores/${storeId}/trace`} replace /> : <p className="muted">Cargando sucursales…</p>;
}

export default function App() {
  return (
    <div className="app">
      <header>
        <h1>Glazed Copilot</h1>
        <nav>
          <NavLink to="/alerts">Alertas</NavLink>
          <NavLink to="/cases">Casos</NavLink>
          <NavLink to="/trace">Inspector</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/alerts" replace />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/trace" element={<TraceRedirect />} />
          <Route path="/stores/:storeId/trace" element={<TracePage />} />
          <Route path="*" element={<p>Página no encontrada</p>} />
        </Routes>
      </main>
    </div>
  );
}
