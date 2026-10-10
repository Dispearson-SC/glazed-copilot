import { useApi } from "./ApiContext";
import { fetchMemories, type Source } from "./data/copilot";
import type { Issue, AlertRecord, MemoryRecord } from "./types";
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

export type MemoryState = "loading" | "ok" | "soon" | "error";

/** Memories of the case (GET /memories). Polled while the page is open so the capsule badge counts the new ones. */
export function useMemoryData(caseId: string, refreshKey = 0) {
  const api = useApi();
  const res = usePolling<Source<MemoryRecord[]> | null>(async () => (caseId ? await fetchMemories(api, caseId) : null), 60_000, true, [caseId, refreshKey]);
  const state: MemoryState = res.data?.status === "ok" ? "ok" : res.data?.status === "soon" ? "soon" : res.error ? "error" : "loading";
  return { records: res.data?.status === "ok" ? res.data.data : null, state: res.data ? state : res.error ? "error" : "loading", refresh: res.refresh };
}
