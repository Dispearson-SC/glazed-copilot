import { useApi } from "./ApiContext";
import { fetchOutlook } from "./data/copilot";
import { shiftDate } from "./format";
import type { DaySummary, DeliveriesResponse, ExpiringResponse, ForecastResponse, InventoryResponse, Kpis, OrderPlan, Outlook } from "./types";
import { usePolling } from "./usePolling";

export interface BranchData {
  forecast: ForecastResponse | null;
  ayer: DaySummary | null;
  hoy: DaySummary | null;
  kpis: Kpis | null;
  expiring: ExpiringResponse | null;
  inventory: InventoryResponse | null;
  deliveries: DeliveriesResponse | null;
  plan: OrderPlan | null;
  outlook: Outlook | null;
  /** Names of the sources that failed (the rest of the window still renders). */
  failed: string[];
}

const ok = <T,>(r: PromiseSettledResult<T>): T | null => (r.status === "fulfilled" ? r.value : null);

/** Everything the Sucursal window shows, one request per source; a failing source never blanks the others. */
export function useBranchData(caseId: string, asOf: string, enabled: boolean, refreshKey = 0) {
  const api = useApi();
  const res = usePolling<BranchData | null>(
    async () => {
      if (!caseId || !asOf || !enabled) return null;
      const names = ["forecast", "ayer", "hoy", "kpis", "expiring", "inventory", "deliveries", "plan", "outlook"] as const;
      const r = await Promise.allSettled([
        api.getForecast(caseId, { from: shiftDate(asOf, -1), to: shiftDate(asOf, 1), level: "store" }),
        api.getDaySummary(caseId, shiftDate(asOf, -1)),
        api.getDaySummary(caseId, asOf),
        api.getKpis(caseId),
        api.getExpiring(caseId),
        api.getInventory(caseId, { limit: "6" }),
        api.getDeliveries(caseId),
        api.getOrderPlan(caseId),
        fetchOutlook(api, caseId),
      ]);
      const outlook = ok(r[8] as PromiseSettledResult<Awaited<ReturnType<typeof fetchOutlook>>>);
      return {
        forecast: ok(r[0]) as ForecastResponse | null,
        ayer: ok(r[1]) as DaySummary | null,
        hoy: ok(r[2]) as DaySummary | null,
        kpis: ok(r[3]) as Kpis | null,
        expiring: ok(r[4]) as ExpiringResponse | null,
        inventory: ok(r[5]) as InventoryResponse | null,
        deliveries: ok(r[6]) as DeliveriesResponse | null,
        plan: ok(r[7]) as OrderPlan | null,
        outlook: outlook?.status === "ok" ? outlook.data : null,
        failed: names.filter((_, i) => r[i].status === "rejected" && names[i] !== "outlook"),
      };
    },
    60_000,
    enabled,
    [caseId, asOf, enabled, refreshKey],
  );
  return { data: res.data, loading: res.loading };
}
