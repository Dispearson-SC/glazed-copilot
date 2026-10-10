import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

interface Session {
  /** Store chosen by the user in the Home selector ("" = none yet). */
  storeId: string;
  setStoreId: (id: string) => void;
  /** Case chosen in the login picker ("" = the store's default live case). */
  caseId: string;
  /** `forStoreId` is the store the case belongs to (the session store may still be unset on first load). */
  setCaseId: (id: string, forStoreId?: string) => void;
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

const caseKey = (storeId: string) => `glazed.caseId.${storeId}`;

/** Last case the manager chose in this store ("" when none or storage is unavailable). */
export function readStoredCase(storeId: string): string {
  try {
    return storeId ? (localStorage.getItem(caseKey(storeId)) ?? "") : "";
  } catch {
    return "";
  }
}

function writeStoredCase(storeId: string, id: string) {
  try {
    if (storeId && id) localStorage.setItem(caseKey(storeId), id);
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
  const storeRef = useRef(storeId);
  storeRef.current = storeId;
  const [caseId, setCaseIdState] = useState("");
  const setCaseId = useCallback((id: string, forStoreId?: string) => {
    writeStoredCase(forStoreId ?? storeRef.current, id);
    setCaseIdState(id);
  }, []);
  const [refreshKey, setKey] = useState(0);
  const bump = useCallback(() => setKey((k) => k + 1), []);
  const value = useMemo(() => ({ storeId, setStoreId, caseId, setCaseId, refreshKey, bump }), [storeId, setStoreId, caseId, setCaseId, refreshKey, bump]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useSession = () => useContext(Ctx);
