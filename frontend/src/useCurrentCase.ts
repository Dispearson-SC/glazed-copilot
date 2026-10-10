import type { Api } from "./api";
import { useApi } from "./ApiContext";
import { DEFAULT_SIM_TODAY } from "./config";
import { readStoredCase, useSession } from "./SessionContext";
import type { Case } from "./types";
import { usePolling } from "./usePolling";

const byAge = (a: Case, b: Case) =>
  (a.created_at ?? "").localeCompare(b.created_at ?? "") || a.case_id.localeCompare(b.case_id);

/** Live cases at `simToday`, oldest first, so every tab picks the same one. */
export const liveAt = (cases: Case[], simToday: string): Case[] =>
  cases.filter((c) => c.mode === "live" && c.sim_today === simToday).sort(byAge);

/** The case a store screen works on: preferred id, else live at the default date, else any live, else the first. */
export const pickCase = (cases: Case[], preferredId = "", defaultSimToday = DEFAULT_SIM_TODAY): Case | null =>
  cases.find((c) => c.case_id === preferredId) ??
  liveAt(cases, defaultSimToday)[0] ??
  cases.find((c) => c.mode === "live") ??
  cases[0] ??
  null;

const inFlight = new Map<string, Promise<Case[]>>();

/** Creates a live case at `simToday` once per store+date (shared across concurrent callers), then re-lists. */
export function ensureCaseAt(api: Api, storeId: string, simToday: string, title = `Demo ${simToday}`): Promise<Case[]> {
  const key = `${storeId}|${simToday}`;
  let p = inFlight.get(key);
  if (!p) {
    p = (async () => {
      await api.createCase({ store_id: storeId, sim_today: simToday, mode: "live", title });
      return api.listCases({ store_id: storeId });
    })().finally(() => inFlight.delete(key));
    inFlight.set(key, p);
  }
  return p;
}

const ensureDefaultCase = (api: Api, storeId: string) => ensureCaseAt(api, storeId, DEFAULT_SIM_TODAY);

export function useCurrentCase(storeId: string, refreshKey = 0) {
  const api = useApi();
  const { caseId } = useSession();
  const res = usePolling(
    async () => {
      if (!storeId) return null;
      const cases = await api.listCases({ store_id: storeId });
      const remembered = caseId ? "" : readStoredCase(storeId);
      if (remembered && cases.some((c) => c.case_id === remembered)) return pickCase(cases, remembered);
      if (caseId || liveAt(cases, DEFAULT_SIM_TODAY).length > 0) return pickCase(cases, caseId);
      try {
        return pickCase(await ensureDefaultCase(api, storeId), caseId);
      } catch {
        return pickCase(cases, caseId);
      }
    },
    60_000,
    false,
    [storeId, refreshKey, caseId],
  );
  return { currentCase: res.data, loading: res.loading, error: res.error };
}
