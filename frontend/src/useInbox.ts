import { useApi } from "./ApiContext";
import type { AgentsStatusResponse, InboxCounts } from "./types";
import { usePolling } from "./usePolling";

/** Capsule badges (GET /cases/{id}/inbox-counts) and the agents line (GET /agents/status). A missing route is simply absent (null). */
export function useInbox(caseId: string, refreshKey = 0) {
  const api = useApi();
  const counts = usePolling<InboxCounts | null>(async () => (caseId ? await api.getInboxCounts(caseId).catch(() => null) : null), 60_000, true, [caseId, refreshKey]);
  const agents = usePolling<AgentsStatusResponse | null>(async () => await api.getAgentsStatus().catch(() => null), 30_000, true, [refreshKey]);
  return { counts: counts.data, agents: agents.data, refreshCounts: counts.refresh };
}
