import FloatingChat from "../chat/FloatingChat";
import { Link } from "react-router-dom";
import { useApi } from "../ApiContext";
import { ErrorBox, StoreSelect, useStores } from "../components";
import BriefingCard from "../dashboard/BriefingCard";
import ContextChips from "../dashboard/ContextChips";
import Hero from "../dashboard/Hero";
import MetricCards from "../dashboard/MetricCards";
import TopProducts from "../dashboard/TopProducts";
import ForecastAccuracy from "../dashboard/ForecastAccuracy";
import ForecastChart from "../dashboard/ForecastChart";
import UpcomingCard from "../dashboard/UpcomingCard";
import TrendChart from "../dashboard/TrendChart";
import { lastSevenDays, shiftDate } from "../dashboard/format";
import { rangeText, usd, wasteMid } from "../issues";
import { useSession } from "../SessionContext";
import { useCurrentCase } from "../useCurrentCase";
import { useOptionalPolling } from "../useOptionalPolling";
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
  const summary = usePolling(() => (caseId ? api.getDaySummary(caseId) : Promise.resolve(null)), 60_000, true, [caseId, session.refreshKey]);
  const day = summary.data?.date;
  const trend = usePolling(
    async () => {
      if (!caseId || !day) return null;
      // The summary date is already loaded; only the six previous days are fetched.
      const prev = lastSevenDays(day).slice(0, 6);
      return [...(await Promise.all(prev.map((d) => api.getDaySummary(caseId, d)))), summary.data!];
    },
    60_000,
    false,
    [caseId, day, session.refreshKey],
  );
  const briefing = usePolling(() => (caseId ? api.getBriefing(caseId) : Promise.resolve(null)), 60_000, true, [caseId, session.refreshKey]);
  const plan = usePolling(() => (caseId ? api.getOrderPlan(caseId) : Promise.resolve(null)), 60_000, true, [caseId, session.refreshKey]);
  const simToday = currentCase?.sim_today;
  const forecast = useOptionalPolling(
    () => (caseId && simToday ? api.getForecast(caseId, { from: shiftDate(simToday, -7), to: shiftDate(simToday, 7), level: "store" }) : Promise.resolve(null)),
    60_000,
    false,
    [caseId, simToday, session.refreshKey],
  );
  const accuracy = useOptionalPolling(
    () => (caseId && forecast.data ? api.getForecastAccuracy(caseId, "shelf_life") : Promise.resolve(null)),
    300_000,
    false,
    [caseId, simToday, session.refreshKey, Boolean(forecast.data)],
  );
  const error = storesError ?? caseError ?? kpis.error ?? alerts.error;
  const summaryError = summary.error;
  const open = (alerts.data ?? []).filter((a) => !CLOSED.includes(a.state));
  const count = (c: string) => open.filter((a) => semaphore(a.severity_usd) === c).length;

  return (
    <section>
      <h2>Inicio</h2>
      <StoreSelect stores={stores} value={storeId} onChange={session.setStoreId} />
      <ErrorBox error={error} />
      <ErrorBox error={summaryError} />
      {summary.data && !summaryError && (
        <div className="flex flex-col gap-space-md">
          <Hero summary={summary.data} />
          <ContextChips context={summary.data.context} />
          <MetricCards summary={summary.data} />
          {forecast.data ? (
            <>
              <ForecastChart forecast={forecast.data} />
              {accuracy.data && <ForecastAccuracy accuracy={accuracy.data} />}
            </>
          ) : (
            <TrendChart days={trend.data} selected={summary.data.date} error={trend.error} />
          )}
          <TopProducts summary={summary.data} />
        </div>
      )}
      {currentCase && <BriefingCard briefing={briefing.data} error={briefing.error} />}
      {currentCase && <UpcomingCard briefing={briefing.data} plan={plan.data} error={plan.error} />}
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
      {currentCase && (
        <FloatingChat
          storeId={storeId}
          caseId={currentCase.case_id}
          storeName={stores.find((s) => s.store_id === storeId)?.display_name}
          simToday={currentCase.sim_today}
        />
      )}
    </section>
  );
}
