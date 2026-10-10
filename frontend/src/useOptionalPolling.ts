import { isUnavailable } from "./api";
import { usePolling } from "./usePolling";

/** Polls a route that may not be deployed yet: 404/501 become `soon`, never an error. */
export function useOptionalPolling<T>(fn: () => Promise<T | null>, intervalMs: number, enabled = true, deps: unknown[] = []) {
  const res = usePolling<{ soon: boolean; data: T | null }>(
    async () => {
      try {
        return { soon: false, data: await fn() };
      } catch (e) {
        if (isUnavailable(e)) return { soon: true, data: null };
        throw e;
      }
    },
    intervalMs,
    enabled,
    deps,
  );
  return { data: res.data?.data ?? null, soon: res.data?.soon ?? false, error: res.error, loading: res.loading, refresh: res.refresh };
}
