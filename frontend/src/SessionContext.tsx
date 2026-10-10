import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

interface Session {
  /** Store chosen by the user in the Home selector ("" = none yet). */
  storeId: string;
  setStoreId: (id: string) => void;
  /** Bumped after the simulated clock advances so pages refetch. */
  refreshKey: number;
  bump: () => void;
}

const Ctx = createContext<Session>({ storeId: "", setStoreId: () => {}, refreshKey: 0, bump: () => {} });

export function SessionProvider({ children }: { children: ReactNode }) {
  const [storeId, setStoreId] = useState("");
  const [refreshKey, setKey] = useState(0);
  const bump = useCallback(() => setKey((k) => k + 1), []);
  const value = useMemo(() => ({ storeId, setStoreId, refreshKey, bump }), [storeId, refreshKey, bump]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useSession = () => useContext(Ctx);
