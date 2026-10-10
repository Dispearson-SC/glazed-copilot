import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

interface Session {
  /** Store chosen by the user in the Home selector ("" = none yet). */
  storeId: string;
  setStoreId: (id: string) => void;
  /** Case chosen in the login picker ("" = the store's default live case). */
  caseId: string;
  setCaseId: (id: string) => void;
  /** Bumped after the simulated clock advances so pages refetch. */
  refreshKey: number;
  bump: () => void;
}

const STORAGE_KEY = "glazed.storeId";

function readStoredStore(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

function writeStoredStore(id: string) {
  try {
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable: the choice just lasts for this session */
  }
}

const Ctx = createContext<Session>({ storeId: "", setStoreId: () => {}, caseId: "", setCaseId: () => {}, refreshKey: 0, bump: () => {} });

export function SessionProvider({ children }: { children: ReactNode }) {
  const [storeId, setStoreIdState] = useState(readStoredStore);
  const setStoreId = useCallback((id: string) => {
    writeStoredStore(id);
    setStoreIdState(id);
  }, []);
  const [caseId, setCaseId] = useState("");
  const [refreshKey, setKey] = useState(0);
  const bump = useCallback(() => setKey((k) => k + 1), []);
  const value = useMemo(() => ({ storeId, setStoreId, caseId, setCaseId, refreshKey, bump }), [storeId, setStoreId, caseId, refreshKey, bump]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useSession = () => useContext(Ctx);
