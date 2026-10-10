import FloatingChat from "../chat/FloatingChat";
import { useApi } from "../ApiContext";
import { ErrorBox, useStores } from "../components";
import Hero from "../dashboard/Hero";
import MetricCards from "../dashboard/MetricCards";
import TopProducts from "../dashboard/TopProducts";
import ForecastChart from "../dashboard/ForecastChart";
import TrendChart from "../dashboard/TrendChart";
import { lastSevenDays, shiftDate } from "../dashboard/format";
import { useSession } from "../SessionContext";
import { useCurrentCase } from "../useCurrentCase";
import { useOptionalPolling } from "../useOptionalPolling";
import { usePolling } from "../usePolling";

export default function HomePage() {
  const api = useApi();
  const session = useSession();
  const { stores, storeId: firstId, error: storesError } = useStores();
  const storeId = session.storeId || firstId;
  const { currentCase, loading, error: caseError } = useCurrentCase(storeId, session.refreshKey);
  const caseId = currentCase?.case_id;
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
  const simToday = currentCase?.sim_today;
  const forecast = useOptionalPolling(
    () => (caseId && simToday ? api.getForecast(caseId, { from: shiftDate(simToday, -7), to: shiftDate(simToday, 7), level: "store" }) : Promise.resolve(null)),
    60_000,
    false,
    [caseId, simToday, session.refreshKey],
  );
  const error = storesError ?? caseError;

  return (
    <section className="flex flex-col gap-space-md">
      <ErrorBox error={error} />
      <ErrorBox error={summary.error} />
      {summary.data && !summary.error && (
        <div className="flex flex-col gap-space-md">
          <Hero summary={summary.data} />
          <MetricCards summary={summary.data} />
          {forecast.data ? (
            <ForecastChart forecast={forecast.data} />
          ) : (
            <TrendChart days={trend.data} selected={summary.data.date} error={trend.error} />
          )}
          <TopProducts summary={summary.data} />
        </div>
      )}
      {!error && !loading && !currentCase && <p className="text-on-surface-variant">Sin caso activo para esta sucursal</p>}
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
