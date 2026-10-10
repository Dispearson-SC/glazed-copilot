import { useApi } from "../ApiContext";
import ActionsFooter from "../components/ActionsFooter";
import ActivityChart, { type ActivityPoint } from "../components/ActivityChart";
import HeroCard from "../components/HeroCard";
import MetricCards from "../components/MetricCards";
import PageHeader from "../components/PageHeader";
import PageShell from "../components/PageShell";
import TopProducts from "../components/TopProducts";
import FloatingChat from "../chat/FloatingChat";
import { ErrorBox, useStores } from "../components";
import { lastSevenDays, shiftDate } from "../format";
import { useSession } from "../SessionContext";
import type { DaySummary, ForecastResponse } from "../types";
import { useCurrentCase } from "../useCurrentCase";
import { useOptionalPolling } from "../useOptionalPolling";
import { usePolling } from "../usePolling";

const PROJECTED_DAYS = 3;

/** 7 actual days ending at `day`, then the next projected days; an actual is never read past `day`. */
function buildPoints(day: string, forecast: ForecastResponse | null, trend: DaySummary[] | null): ActivityPoint[] {
  const actuals = lastSevenDays(day).map((date): ActivityPoint => {
    const kind = date === day ? "today" : "actual";
    const value = forecast
      ? (forecast.points.find((p) => p.date === date)?.actual ?? null)
      : (trend?.find((d) => d.date === date)?.totals?.net_sales ?? null);
    return value == null ? { date, kind: "nodata", value: null } : { date, kind, value };
  });
  const future = (forecast?.points ?? [])
    .filter((p) => p.date > day)
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, PROJECTED_DAYS)
    .map((p): ActivityPoint => ({ date: p.date, kind: "forecast", value: p.forecast }));
  return [...actuals, ...future];
}

export default function DashboardPage() {
  const api = useApi();
  const session = useSession();
  const { stores, storeId: firstId, error: storesError } = useStores();
  const storeId = session.storeId || firstId;
  const { currentCase, loading, error: caseError } = useCurrentCase(storeId, session.refreshKey);
  const caseId = currentCase?.case_id;
  const simToday = currentCase?.sim_today;
  const summary = usePolling(() => (caseId ? api.getDaySummary(caseId) : Promise.resolve(null)), 60_000, true, [caseId, session.refreshKey]);
  const day = summary.data?.date;
  const forecast = useOptionalPolling(
    () => (caseId && simToday ? api.getForecast(caseId, { from: shiftDate(simToday, -7), to: shiftDate(simToday, 7), level: "store" }) : Promise.resolve(null)),
    60_000,
    false,
    [caseId, simToday, session.refreshKey],
  );
  // Without a forecast the chart falls back to actuals only; the six earlier days come from day summaries.
  const needTrend = !forecast.loading && !forecast.data;
  const trend = usePolling(
    async () => {
      if (!needTrend || !caseId || !day) return null;
      const prev = lastSevenDays(day).slice(0, 6);
      return [...(await Promise.all(prev.map((d) => api.getDaySummary(caseId, d)))), summary.data!];
    },
    60_000,
    false,
    [caseId, day, session.refreshKey, needTrend],
  );
  const error = storesError ?? caseError;
  const data = summary.data;
  const ready = Boolean(data) && !summary.error;
  const points = ready && day ? buildPoints(day, forecast.data, trend.data) : [];
  const store = stores.find((s) => s.store_id === storeId);

  return (
    <PageShell
      subtitle="Resumen"
      columnClass="flex flex-col w-full space-y-space-lg max-w-[1024px] mx-auto"
      floating={
        currentCase ? (
          <FloatingChat storeId={storeId} caseId={currentCase.case_id} storeName={store?.display_name} simToday={currentCase.sim_today} />
        ) : null
      }
    >
      <ErrorBox error={error} />
      <ErrorBox error={summary.error} />
      {ready && data && (
        <>
          <PageHeader date={data.date} simToday={simToday ?? data.as_of} />
          <HeroCard summary={data} />
          <MetricCards summary={data} />
          {(forecast.data || trend.data) && <ActivityChart points={points} model={forecast.data?.model} />}
          <TopProducts summary={data} />
          <ActionsFooter asOf={data.as_of} />
        </>
      )}
      {!error && !loading && !currentCase && (
        <p className="font-body-md text-body-md text-on-surface-variant">Sin caso activo para esta sucursal</p>
      )}
    </PageShell>
  );
}
