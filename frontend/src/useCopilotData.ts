import { useMemo } from "react";
import { useApi } from "./ApiContext";
import { buildDecisionItems, type DecisionItem } from "./data/copilot";
import { usePolling } from "./usePolling";

/**
 * Decisions of a case from GET /issues, GET /order-plan and GET /proposals.
 * The issues and the order plan are fetched first because the backend only accepts proposals for what it served to the case.
 */
export function useCopilotData(caseId: string, simToday: string, refreshKey = 0) {
  const api = useApi();
  const res = usePolling(
    async () => {
      if (!caseId) return null;
      const [issues, plan] = await Promise.all([api.listIssues(caseId, { limit: "50" }), api.getOrderPlan(caseId).catch(() => null)]);
      const proposals = await api.listProposals({ case_id: caseId });
      return { issues, plan, proposals };
    },
    60_000,
    true,
    [caseId, refreshKey],
  );
  const items: DecisionItem[] = useMemo(
    () => (res.data ? buildDecisionItems({ ...res.data, simToday }) : []),
    [res.data, simToday],
  );
  return { items, loading: res.loading, error: res.error, refresh: res.refresh };
}
