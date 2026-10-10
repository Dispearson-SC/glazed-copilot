import { createContext, useContext, type ReactNode } from "react";
import { api as defaultApi, type Api } from "./api";

const Ctx = createContext<Api>(defaultApi);

export function ApiProvider({ api, children }: { api: Api; children: ReactNode }) {
  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

export const useApi = () => useContext(Ctx);
