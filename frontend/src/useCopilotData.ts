import { useMemo } from "react";
import { useApi } from "./ApiContext";
import { buildPendingItems, type DecisionItem } from "./data/copilot";
import { usePolling } from "./usePolling";

/** Decisions of a case from GET /cases/{id}/decisions/pending (the backend splits approvals and technical and hides what is decided). */
export function useCopilotData(caseId: string, simToday: string, refreshKey = 0) {
  const api = useApi();
  const res = usePolling(async () => (caseId ? await api.getPending(caseId) : null), 60_000, true, [caseId, refreshKey]);
  const items: DecisionItem[] = useMemo(() => buildPendingItems(res.data, simToday), [res.data, simToday]);
  return { items, loading: res.loading, error: res.error, refresh: res.refresh };
}
