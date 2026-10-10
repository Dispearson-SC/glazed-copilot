import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useApi } from "./ApiContext";
import { ApiError, type AuthUser } from "./api";
import LoginPage from "./pages/LoginPage";
import type { Store } from "./types";

interface Auth {
  /** Signed-in user; null when nobody is (or auth is not in use). */
  user: AuthUser | null;
  logout: () => Promise<void>;
}

const Ctx = createContext<Auth>({ user: null, logout: async () => {} });

export const useAuth = () => useContext(Ctx);

/** Admins (any store_ids, [] = all) and no-auth see every store; a manager sees only their stores, and none when unassigned. */
export function scopeStores(stores: Store[], user: AuthUser | null): Store[] {
  if (!user || user.role !== "manager") return stores;
  const allowed = Array.isArray(user.store_ids) ? user.store_ids : [];
  return stores.filter((s) => allowed.includes(s.store_id));
}

/** True when the user is pinned to one store: the selector is read-only. */
export const isSingleStore = (user: AuthUser | null): boolean =>
  !!user && user.role === "manager" && Array.isArray(user.store_ids) && user.store_ids.length === 1;

type Status = "loading" | "ready" | "login" | "error";

/**
 * Decides whether to show the app or the login.
 * Health says whether auth is required; a backend without the field (or without health) means it is not.
 * When required: /auth/me 200 -> app, 401 -> login, 404/501 -> app, network error -> login with retry.
 * When not required: /auth/me is only asked to show the user when it happens to answer 200.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const api = useApi();
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const required = useRef(false);
  const statusRef = useRef<Status>("loading");
  statusRef.current = status;
  const [demo, setDemo] = useState(false);

  const check = useCallback(async () => {
    setStatus("loading");
    let req = false;
    try {
      const h = await api.getHealth();
      req = h.auth_required === true;
      setDemo(h.demo_login === true);
    } catch {
      req = false;
      setDemo(false);
    }
    required.current = req;
    try {
      const { user: u } = await api.me();
      setUser(u);
      setStatus("ready");
    } catch (e) {
      if (!req) setStatus("ready");
      else if (e instanceof ApiError && e.status === 401) setStatus("login");
      else if (e instanceof ApiError && (e.status === 404 || e.status === 501)) setStatus("ready");
      else setStatus("error");
    }
  }, [api]);

  useEffect(() => {
    void check();
  }, [check]);

  useEffect(() => {
    api.setOnUnauthorized?.(() => {
      // Ignore 401s while loading or already on the login: only a live session can expire.
      if (!required.current || statusRef.current !== "ready") return;
      setUser(null);
      setStatus("login");
    });
    return () => api.setOnUnauthorized?.(null);
  }, [api]);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* the local session ends either way */
    }
    setUser(null);
    setStatus("login");
  }, [api]);

  const value = useMemo(() => ({ user, logout }), [user, logout]);

  if (status === "loading") {
    return (
      <div role="status" aria-busy="true" aria-label="Cargando sesión" className="flex min-h-screen items-center justify-center bg-surface">
        <img alt="" src="/Logo.png" className="h-16 w-16 animate-pulse rounded-full object-contain" />
      </div>
    );
  }
  if (status === "login" || status === "error") {
    return (
      <LoginPage
        onLogin={(u) => {
          setUser(u);
          setStatus("ready");
        }}
        demo={demo}
        loadFailed={status === "error"}
        onRetry={() => void check()}
      />
    );
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
