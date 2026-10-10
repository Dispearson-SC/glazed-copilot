import { useApi } from "./ApiContext";
import type { Case } from "./types";
import { usePolling } from "./usePolling";

/** The case a store screen works on: the first live case, else the first one. */
export const pickCase = (cases: Case[]): Case | null => cases.find((c) => c.mode === "live") ?? cases[0] ?? null;

export function useCurrentCase(storeId: string, refreshKey = 0) {
  const api = useApi();
  const res = usePolling(
    async () => (storeId ? pickCase(await api.listCases({ store_id: storeId })) : null),
    60_000,
    false,
    [storeId, refreshKey],
  );
  return { currentCase: res.data, loading: res.loading, error: res.error };
}
