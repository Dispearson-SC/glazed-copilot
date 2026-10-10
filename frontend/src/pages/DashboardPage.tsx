import { useEffect, useState } from "react";
import { useApi } from "../ApiContext";
import ActionsFooter from "../components/ActionsFooter";
import ActivityChart from "../components/ActivityChart";
import HeroCard from "../components/HeroCard";
import MetricCards from "../components/MetricCards";
import PageHeader from "../components/PageHeader";
import PageShell from "../components/PageShell";
import TopProducts from "../components/TopProducts";
import FloatingChat from "../chat/FloatingChat";
import { ErrorBox, useStores } from "../components";
import { shiftDate } from "../format";
import { useSession } from "../SessionContext";
import { useCurrentCase } from "../useCurrentCase";
import { usePolling } from "../usePolling";

/** Whole minutes since `stamp` last changed (null before the first load). */
function useMinutesAgo(stamp: unknown): number | null {
  const [at, setAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (stamp) setAt(Date.now());
  }, [stamp]);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);
  return at == null ? null : Math.max(0, Math.floor((now - at) / 60_000));
}

export default function DashboardPage() {
  const api = useApi();
  const session = useSession();
  const { stores, storeId: firstId, error: storesError } = useStores();
  const storeId = session.storeId || firstId;
  const { currentCase, loading, error: caseError } = useCurrentCase(storeId, session.refreshKey);
  const caseId = currentCase?.case_id;
  const simToday = currentCase?.sim_today;
  // "Today" is the case's simulated day (as_of): complete, never the day before.
  const summary = usePolling(
    () => (caseId && simToday ? api.getDaySummary(caseId, simToday) : Promise.resolve(null)),
    60_000,
    true,
    [caseId, simToday, session.refreshKey],
  );
  // Yesterday feeds the "vs ayer" delta.
  const ayer = usePolling(
    () => (caseId && simToday ? api.getDaySummary(caseId, shiftDate(simToday, -1)).catch(() => null) : Promise.resolve(null)),
    60_000,
    true,
    [caseId, simToday, session.refreshKey],
  );
  const minutesAgo = useMinutesAgo(summary.data);
  const error = storesError ?? caseError;
  const data = summary.data;
  const ready = Boolean(data) && !summary.error;
  const store = stores.find((s) => s.store_id === storeId);

  return (
    <PageShell
      columnClass="flex flex-col w-full space-y-space-lg max-w-[1024px] mx-auto"
      floating={currentCase ? <FloatingChat storeId={storeId} caseId={currentCase.case_id} storeName={store?.display_name} /> : null}
    >
      <ErrorBox error={error} />
      <ErrorBox error={summary.error} />
      {ready && data && currentCase && (
        <>
          <PageHeader date={data.date} mode={currentCase.mode} />
          <HeroCard summary={data} ayer={ayer.data} />
          <MetricCards summary={data} />
          <ActivityChart />
          <TopProducts summary={data} />
          <ActionsFooter minutesAgo={minutesAgo} />
        </>
      )}
      {!error && !loading && !currentCase && (
        <p className="font-body-md text-body-md text-on-surface-variant">Sin caso activo para esta sucursal</p>
      )}
    </PageShell>
  );
}
