import { useCallback, useEffect, useRef, useState } from "react";

/** Calls `fn` immediately (and again when `deps` change) and every `intervalMs` while `enabled`. Keeps the last good data on errors. */
export function usePolling<T>(fn: () => Promise<T>, intervalMs: number, enabled = true, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const refresh = useCallback(async () => {
    try {
      setData(await fnRef.current());
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh, ...deps]);

  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => void refresh(), intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs, enabled]);

  return { data, error, loading, refresh };
}
