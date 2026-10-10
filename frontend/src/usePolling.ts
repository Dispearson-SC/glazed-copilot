import { useCallback, useEffect, useRef, useState } from "react";

export interface PollingOptions {
  /** Keep the last data while `deps` change (default false: data of another scope is dropped and `loading` is true again). */
  keepOnChange?: boolean;
}

/**
 * Calls `fn` immediately (and again when `deps` change) and every `intervalMs` while `enabled`. Keeps the last good data on errors.
 * An answer that arrives after `deps` changed (or after unmount) is ignored, so a slow response for an old case can never replace the new one.
 */
export function usePolling<T>(fn: () => Promise<T>, intervalMs: number, enabled = true, deps: unknown[] = [], opts: PollingOptions = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const scope = useRef(0); // bumped whenever deps change or the component unmounts

  const refresh = useCallback(async () => {
    const mine = scope.current;
    try {
      const value = await fnRef.current();
      if (mine !== scope.current) return;
      setData(value);
      setError(null);
    } catch (e) {
      if (mine !== scope.current) return;
      setError(e as Error);
    } finally {
      if (mine === scope.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    scope.current++;
    if (!opts.keepOnChange) {
      setData(null);
      setError(null);
      setLoading(true);
    }
    void refresh();
    return () => {
      scope.current++;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh, ...deps]);

  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => void refresh(), intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs, enabled]);

  return { data, error, loading, refresh };
}
