import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, createApi } from "./api";

function mockFetch(body: unknown, status = 200) {
  const fn = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  return fn;
}

describe("api client", () => {
  let fetchFn: ReturnType<typeof mockFetch>;
  beforeEach(() => {
    fetchFn = mockFetch([]);
  });

  it("builds GET urls with query params and drops undefined", async () => {
    const api = createApi("http://x:1", fetchFn as unknown as typeof fetch);
    await api.listAlerts({ store_id: "S030", state: undefined });
    expect(fetchFn).toHaveBeenCalledWith("http://x:1/api/v1/alerts?store_id=S030", expect.anything());
  });

  it("uses a relative base when the base url is empty", async () => {
    const api = createApi("", fetchFn as unknown as typeof fetch);
    await api.listStores();
    expect((fetchFn.mock.calls[0] as unknown as [string])[0]).toBe("/api/v1/stores");
  });

  it("PATCHes alert state as JSON", async () => {
    const api = createApi("", fetchFn as unknown as typeof fetch);
    await api.setAlertState("a1", "vista");
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/alerts/a1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ state: "vista" });
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("POSTs a proposal decision", async () => {
    const api = createApi("", fetchFn as unknown as typeof fetch);
    await api.decide("p1", { approved: false, reason: "no budget" });
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/proposals/p1/decision");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ approved: false, reason: "no budget" });
  });

  it("creates, forks and messages cases", async () => {
    const api = createApi("", fetchFn as unknown as typeof fetch);
    await api.createCase({ store_id: "S030", sim_today: "2026-03-01", mode: "live" });
    await api.forkCase("c1", { title: "what-if" });
    await api.sendMessage("c1", "hola");
    await api.getTurn("c1", "t1");
    const urls = fetchFn.mock.calls.map((c) => (c as unknown as [string])[0]);
    expect(urls).toEqual([
      "/api/v1/cases",
      "/api/v1/cases/c1/fork",
      "/api/v1/cases/c1/messages",
      "/api/v1/cases/c1/turns/t1",
    ]);
  });

  it("queries trace and proposals", async () => {
    const api = createApi("", fetchFn as unknown as typeof fetch);
    await api.getTrace("S030", "c1");
    await api.listProposals({ case_id: "c1", status: "pending" });
    const urls = fetchFn.mock.calls.map((c) => (c as unknown as [string])[0]);
    expect(urls).toEqual([
      "/api/v1/trace?store_id=S030&case_id=c1",
      "/api/v1/proposals?case_id=c1&status=pending",
    ]);
  });

  it("throws ApiError with the backend detail on 4xx", async () => {
    const api = createApi("", mockFetch({ detail: "nope" }, 422) as unknown as typeof fetch);
    await expect(api.listStores()).rejects.toMatchObject({ status: 422, message: "nope" });
    await expect(api.listStores()).rejects.toBeInstanceOf(ApiError);
  });

  it("wraps network failures in ApiError with status 0", async () => {
    const failing = vi.fn(async () => {
      throw new TypeError("failed to fetch");
    });
    const api = createApi("", failing as unknown as typeof fetch);
    await expect(api.listStores()).rejects.toMatchObject({ status: 0 });
  });
});

describe("api client (Wave 5)", () => {
  it("GETs order plan and kpis for a case", async () => {
    const fetchFn = mockFetch({});
    const api = createApi("", fetchFn as unknown as typeof fetch);
    await api.getOrderPlan("c1");
    await api.getKpis("c1");
    const urls = fetchFn.mock.calls.map((c) => (c as unknown as [string])[0]);
    expect(urls).toEqual(["/api/v1/cases/c1/order-plan", "/api/v1/cases/c1/kpis"]);
  });

  it("POSTs advance with a default of one day", async () => {
    const fetchFn = mockFetch({ sim_today: "2026-03-02", new_alerts: [] });
    const api = createApi("", fetchFn as unknown as typeof fetch);
    await api.advance("c1");
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/cases/c1/advance");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ days: 1 });
  });

  it("proposes an option by id only (backend copies params and tier)", async () => {
    const fetchFn = mockFetch({});
    const api = createApi("", fetchFn as unknown as typeof fetch);
    await api.proposeOption({ case_id: "c1", issue_id: "i1", option_id: "o1", rationale: "x" });
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/proposals");
    expect(JSON.parse(init.body as string)).toEqual({ case_id: "c1", issue_id: "i1", option_id: "o1", rationale: "x" });
  });
});
