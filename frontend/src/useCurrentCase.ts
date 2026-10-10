import { useApi } from "./ApiContext";
import { useSession } from "./SessionContext";
import type { Case } from "./types";
import { usePolling } from "./usePolling";

/** The case a store screen works on: the first live case, else the first one. */
export const pickCase = (cases: Case[], preferredId = ""): Case | null =>
  cases.find((c) => c.case_id === preferredId) ?? cases.find((c) => c.mode === "live") ?? cases[0] ?? null;

export function useCurrentCase(storeId: string, refreshKey = 0) {
  const api = useApi();
  const { caseId } = useSession();
  const res = usePolling(
    async () => (storeId ? pickCase(await api.listCases({ store_id: storeId }), caseId) : null),
    60_000,
    false,
    [storeId, refreshKey, caseId],
  );
  return { currentCase: res.data, loading: res.loading, error: res.error };
}
