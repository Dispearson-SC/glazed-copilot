import { Link } from "react-router-dom";
import { useApi } from "../ApiContext";
import { ErrorBox, StoreSelect, useStores } from "../components";
import { rangeText, usd, wasteMid } from "../issues";
import { useSession } from "../SessionContext";
import { useCurrentCase } from "../useCurrentCase";
import { usePolling } from "../usePolling";

const CLOSED = ["resuelta", "descartada", "cerrada"];
export const semaphore = (severity: number) => (severity >= 500 ? "red" : severity >= 100 ? "yellow" : "green");

export default function HomePage() {
  const api = useApi();
  const session = useSession();
  const { stores, storeId: firstId, error: storesError } = useStores();
  const storeId = session.storeId || firstId;
  const { currentCase, loading, error: caseError } = useCurrentCase(storeId, session.refreshKey);
  const caseId = currentCase?.case_id;
  const kpis = usePolling(() => (caseId ? api.getKpis(caseId) : Promise.resolve(null)), 30_000, true, [caseId, session.refreshKey]);
  const alerts = usePolling(() => (storeId ? api.listAlerts({ store_id: storeId }) : Promise.resolve([])), 30_000, true, [
    storeId,
    session.refreshKey,
  ]);
  const error = storesError ?? caseError ?? kpis.error ?? alerts.error;
  const open = (alerts.data ?? []).filter((a) => !CLOSED.includes(a.state));
  const count = (c: string) => open.filter((a) => semaphore(a.severity_usd) === c).length;

  return (
    <section>
      <h2>Inicio</h2>
      <StoreSelect stores={stores} value={storeId} onChange={session.setStoreId} />
      <ErrorBox error={error} />
      {!error && !loading && !currentCase && <p className="muted">Sin caso activo para esta sucursal</p>}
      {kpis.data && (
        <>
          <h3>
            Lo que se pierde{kpis.data.window ? ` (${kpis.data.window.from} a ${kpis.data.window.to})` : ""}
          </h3>
          <div className="losses">
            <div className="card loss" data-testid="loss-waste">
              <div className="muted">Merma</div>
              <div className="big">{usd(wasteMid(kpis.data.waste_usd))}</div>
            </div>
            <div className="card loss" data-testid="loss-lost-sales">
              <div className="muted">Ventas perdidas</div>
              <div className="big">{usd(kpis.data.lost_sales_usd.mid)}</div>
              <div className="muted">{rangeText(kpis.data.lost_sales_usd)}</div>
            </div>
          </div>
        </>
      )}
      <h3>Alertas abiertas</h3>
      <div className="losses">
        <span className="light red" data-testid="sem-red">{count("red")}</span> alta
        <span className="light yellow" data-testid="sem-yellow">{count("yellow")}</span> media
        <span className="light green" data-testid="sem-green">{count("green")}</span> baja
      </div>
      <p>
        <Link to={`/stores/${storeId}/purchases`}>Ver compras</Link> · <Link to="/alerts">Ver alertas</Link>
      </p>
    </section>
  );
}
