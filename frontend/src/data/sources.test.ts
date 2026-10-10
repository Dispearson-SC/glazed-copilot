import { describe, expect, it, vi } from "vitest";
import type { Api } from "../api";
import * as src from "./copilot";

const api = {} as Api;

describe("data sources the backend does not serve yet", () => {
  it("answers 'soon' without calling the API", async () => {
    const spy = vi.fn();
    const probe = new Proxy({}, { get: () => spy }) as unknown as Api;
    const calls = await Promise.all([
      src.fetchForecastMetric(probe, "c1", "traffic"),
      src.fetchInventoryStatus(probe, "c1"),
      src.fetchMemories(probe, "c1"),
      src.fetchAutonomyLog(probe, "c1"),
      src.revertAutonomy(probe, "c1", "x"),
      src.fetchAgentsStatus(probe),
      src.fetchTurnProgress(probe, "c1", "t1"),
      src.fetchInboxCounts(probe, "c1"),
    ]);
    for (const c of calls) expect(c).toEqual({ status: "soon" });
    expect(spy).not.toHaveBeenCalled();
  });

  it("treats a 404 on /outlook as 'soon' and passes a 200 through", async () => {
    const { ApiError } = await import("../api");
    const ok = { getOutlook: vi.fn(async () => ({ days: [] })) } as unknown as Api;
    expect(await src.fetchOutlook(ok, "c1")).toEqual({ status: "ok", data: { days: [] } });
    const nf = { getOutlook: vi.fn(async () => { throw new ApiError(404, "Not Found"); }) } as unknown as Api;
    expect(await src.fetchOutlook(nf, "c1")).toEqual({ status: "soon" });
    const boom = { getOutlook: vi.fn(async () => { throw new ApiError(500, "x"); }) } as unknown as Api;
    await expect(src.fetchOutlook(boom, "c1")).rejects.toThrow("x");
  });

  it("exposes an alert's agent as unknown until the API carries agent_id", () => {
    expect(src.alertAgent({ alert_id: "a" } as never)).toBeNull();
    expect(api).toBeDefined();
  });
});
