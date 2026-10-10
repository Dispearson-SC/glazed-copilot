import { useApi } from "./ApiContext";
import type { Issue, AlertRecord, HistoryResponse, SupplierPerformance } from "./types";
import { usePolling } from "./usePolling";

/** Open alerts of the store plus the integrity issues of the case. Kept on while the page is open so the capsule badge is right. */
export function useWarningsData(storeId: string, caseId: string, refreshKey = 0) {
  const api = useApi();
  const res = usePolling<{ alerts: AlertRecord[]; integrity: Issue[] } | null>(
    async () => {
      if (!storeId || !caseId) return null;
      const [alerts, integrity] = await Promise.allSettled([
        api.listAlerts({ store_id: storeId, state: "nueva" }),
        api.listIssues(caseId, { category: "integrity", limit: "50" }),
      ]);
      return { alerts: alerts.status === "fulfilled" ? alerts.value : [], integrity: integrity.status === "fulfilled" ? integrity.value : [] };
    },
    60_000,
    true,
    [storeId, caseId, refreshKey],
  );
  return res.data;
}

/** Decision log and supplier performance for the Memorias window. A failing source is simply absent. */
export function useMemoryData(caseId: string, enabled: boolean, refreshKey = 0) {
  const api = useApi();
  const res = usePolling<{ history: HistoryResponse | null; suppliers: SupplierPerformance[] | null } | null>(
    async () => {
      if (!caseId || !enabled) return null;
      const [history, suppliers] = await Promise.allSettled([api.getHistory(caseId), api.getSupplierPerformance(caseId)]);
      return { history: history.status === "fulfilled" ? history.value : null, suppliers: suppliers.status === "fulfilled" ? suppliers.value : null };
    },
    60_000,
    enabled,
    [caseId, enabled, refreshKey],
  );
  return { data: res.data, loading: res.loading };
}
