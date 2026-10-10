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
    await api.listCases({ store_id: "S030" });
    expect(fetchFn).toHaveBeenCalledWith("http://x:1/api/v1/cases?store_id=S030", expect.anything());
    await api.getDaySummary("c1", undefined);
    expect(fetchFn).toHaveBeenLastCalledWith("http://x:1/api/v1/cases/c1/day-summary", expect.anything());
  });

  it("sends credentials and reports 401s from non-auth routes only", async () => {
    const f = vi.fn(async () => new Response("{}", { status: 401 }));
    const api = createApi("http://x:1", f as unknown as typeof fetch);
    const cb = vi.fn();
    api.setOnUnauthorized(cb);
    await expect(api.listStores()).rejects.toBeInstanceOf(ApiError);
    expect(f).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ credentials: "include" }));
    expect(cb).toHaveBeenCalledTimes(1);
    await expect(api.me()).rejects.toBeInstanceOf(ApiError);
    await expect(api.login({ email: "a", password: "b" })).rejects.toBeInstanceOf(ApiError);
    await expect(api.getHealth()).rejects.toBeInstanceOf(ApiError);
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("uses a relative base when the base url is empty", async () => {
    const api = createApi("", fetchFn as unknown as typeof fetch);
    await api.listStores();
    expect((fetchFn.mock.calls[0] as unknown as [string])[0]).toBe("/api/v1/stores");
  });

  it("POSTs a proposal decision", async () => {
    const api = createApi("", fetchFn as unknown as typeof fetch);
    await api.decide("p1", { approved: false, reason: "no budget" });
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/proposals/p1/decision");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ approved: false, reason: "no budget" });
  });

  it("sends extra headers such as Idempotency-Key on decisions and keeps defaults", async () => {
    const api = createApi("", fetchFn as unknown as typeof fetch);
    await api.decide("p1", { approved: true }, { idempotencyKey: "k-1" });
    const [, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.headers).toMatchObject({ "Idempotency-Key": "k-1", "Content-Type": "application/json", Accept: "application/json" });
  });

  it("creates, forks and messages cases", async () => {
    const api = createApi("", fetchFn as unknown as typeof fetch);
    await api.createCase({ store_id: "S030", sim_today: "2026-03-01", mode: "live" });
    await api.sendMessage("c1", "hola");
    await api.getTurn("c1", "t1");
    const urls = fetchFn.mock.calls.map((c) => (c as unknown as [string])[0]);
    expect(urls).toEqual([
      "/api/v1/cases",
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

describe("resolveBase", () => {
  it("turns a same-origin base into the page origin without embedded credentials", async () => {
    const { resolveBase } = await import("./api");
    expect(resolveBase("", "https://glazed.farone.cloud")).toBe("https://glazed.farone.cloud");
  });
  it("keeps an explicit API URL", async () => {
    const { resolveBase } = await import("./api");
    expect(resolveBase("http://localhost:8100/", "https://x")).toBe("http://localhost:8100/");
  });
});

describe("forecast api", () => {
  it("GETs the forecast with sku/from/to/level and detects unavailable routes", async () => {
    const f = vi.fn(async () => new Response("{}", { status: 200 }));
    const api = createApi("", f as unknown as typeof fetch);
    await api.getForecast("c1", { from: "2026-02-23", to: "2026-03-08", level: "store" });
    expect((f.mock.calls[0] as unknown as [string])[0]).toBe("/api/v1/cases/c1/forecast?from=2026-02-23&to=2026-03-08&level=store");
    const { isUnavailable } = await import("./api");
    expect(isUnavailable(new ApiError(404, "x"))).toBe(true);
    expect(isUnavailable(new ApiError(501, "x"))).toBe(true);
    expect(isUnavailable(new ApiError(500, "x"))).toBe(false);
    expect(isUnavailable(new Error("x"))).toBe(false);
  });
});

describe("wave 14 routes", () => {
  const setup = () => {
    const f = vi.fn(async () => new Response("{}", { status: 200 }));
    return { f, api: createApi("", f as unknown as typeof fetch), url: (i = 0) => (f.mock.calls[i] as unknown as [string])[0], init: (i = 0) => (f.mock.calls[i] as unknown as [string, RequestInit])[1] };
  };

  it("sends the chat context as a field of POST /messages", async () => {
    const { api, url, init } = setup();
    await api.sendMessage("c1", "Analiza", { issue_id: "S1|x|1", option_id: "o1", mode: "analizar" });
    expect(url()).toBe("/api/v1/cases/c1/messages");
    expect(JSON.parse(init().body as string)).toEqual({ text: "Analiza", context: { issue_id: "S1|x|1", option_id: "o1", mode: "analizar" } });
  });

  it("omits the context when there is none", async () => {
    const { api, init } = setup();
    await api.sendMessage("c1", "hola");
    expect(JSON.parse(init().body as string)).toEqual({ text: "hola" });
  });

  it("GETs pending decisions, an issue analysis (id encoded), inbox counts, agents status and memories", async () => {
    const { api, f, url } = setup();
    await api.getPending("c1");
    await api.getAnalysis("c1", "S1|stockout_risk|SKU-1");
    await api.getInboxCounts("c1");
    await api.getAgentsStatus();
    await api.getMemories("c1", { category: "proveedores", q: "pan" });
    await api.getForecast("c1", { metric: "footfall", level: "store" });
    expect(f.mock.calls.map((c) => (c as unknown as [string])[0])).toEqual([
      "/api/v1/cases/c1/decisions/pending",
      "/api/v1/cases/c1/issues/S1%7Cstockout_risk%7CSKU-1/analysis",
      "/api/v1/cases/c1/inbox-counts",
      "/api/v1/agents/status",
      "/api/v1/cases/c1/memories?category=proveedores&q=pan",
      "/api/v1/cases/c1/forecast?metric=footfall&level=store",
    ]);
    expect(url(0)).toContain("pending");
  });

  it("POSTs the atomic decision with the Idempotency-Key header", async () => {
    const { api, url, init } = setup();
    await api.recordDecision("c1", { issue_id: "i1", option_id: "o1", approved: false, reason: "caro" }, { idempotencyKey: "k-9" });
    expect(url()).toBe("/api/v1/cases/c1/decisions");
    expect(init().method).toBe("POST");
    expect(init().headers).toMatchObject({ "Idempotency-Key": "k-9" });
    expect(JSON.parse(init().body as string)).toEqual({ issue_id: "i1", option_id: "o1", approved: false, reason: "caro" });
  });

  it("transcribe posts multipart without a JSON content-type; speak returns the audio blob", async () => {
    const f = vi.fn(async (url: string, _init?: RequestInit) =>
      url.endsWith("/voice/speak") ? new Response("mp3", { headers: { "Content-Type": "audio/mpeg" } }) : new Response(JSON.stringify({ text: "hola" })),
    );
    const api = createApi("http://x:1", f as unknown as typeof fetch);
    await expect(api.transcribe(new Blob(["a"]), "voice.webm")).resolves.toEqual({ text: "hola" });
    const init = f.mock.calls[0][1] as unknown as RequestInit;
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("audio")).toBeInstanceOf(Blob);
    expect((init.body as FormData).get("language")).toBe("es");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
    expect(init.credentials).toBe("include");
    const blob = await api.speak("hola");
    expect(blob.size).toBe(3);
    const sp = f.mock.calls[1][1] as unknown as RequestInit;
    expect(sp.body).toBe(JSON.stringify({ text: "hola" }));
    expect((sp.headers as Record<string, string>).Accept).toBe("audio/mpeg");
  });
});
