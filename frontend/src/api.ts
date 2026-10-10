import type { AlertRecord, Case, CaseMode, DaySummary, DeliveriesResponse, ExpiringResponse, InventoryResponse, Kpis, Outlook, Execution, ForecastResponse, Issue, OrderPlan, Proposal, Store, TraceEvent, Turn, TurnRecord } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type Query = Record<string, string | undefined>;

function qs(query?: Query): string {
  if (!query) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== "") p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** The route is not deployed yet (404) or not implemented (501). */
export const isUnavailable = (e: unknown): boolean => e instanceof ApiError && (e.status === 404 || e.status === 501);

export function createApi(baseUrl: string, fetchFn: typeof fetch = (...a) => fetch(...a)) {
  const base = baseUrl.replace(/\/$/, "");

  async function request<T>(path: string, init: RequestInit = {}, query?: Query): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (init.body !== undefined) headers["Content-Type"] = "application/json";
    Object.assign(headers, init.headers as Record<string, string> | undefined);
    let res: Response;
    try {
      res = await fetchFn(`${base}/api/v1${path}${qs(query)}`, { ...init, headers });
    } catch (e) {
      throw new ApiError(0, `No se pudo conectar con el backend (${(e as Error).message})`);
    }
    if (!res.ok) {
      let detail = res.statusText || `HTTP ${res.status}`;
      try {
        const body = await res.json();
        if (body && typeof body.detail === "string") detail = body.detail;
      } catch {
        /* keep default detail */
      }
      throw new ApiError(res.status, detail);
    }
    return (await res.json()) as T;
  }

  const send = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

  return {
    listStores: () => request<Store[]>("/stores"),
    listCases: (query: { store_id?: string }) => request<Case[]>("/cases", {}, query),
    createCase: (b: { store_id: string; sim_today: string; mode?: CaseMode; title?: string }) =>
      request<Case>("/cases", send("POST", b)),
    sendMessage: (caseId: string, text: string) =>
      request<{ turn_id: string }>(`/cases/${caseId}/messages`, send("POST", { text })),
    listTurns: (caseId: string) => request<TurnRecord[]>(`/cases/${caseId}/turns`),
    getTurn: (caseId: string, turnId: string) => request<Turn>(`/cases/${caseId}/turns/${turnId}`),
    listProposals: (query: { case_id?: string; status?: string }) =>
      request<Proposal[]>("/proposals", {}, query),
    decide: (proposalId: string, b: { approved: boolean; reason?: string }, opts: { idempotencyKey?: string } = {}) =>
      request<Execution>(`/proposals/${proposalId}/decision`, {
        ...send("POST", b),
        ...(opts.idempotencyKey ? { headers: { "Idempotency-Key": opts.idempotencyKey } } : {}),
      }),
    listIssues: (caseId: string, q: { limit?: string; category?: string; kind?: string } = {}) =>
      request<Issue[]>(`/cases/${caseId}/issues`, {}, q),
    getKpis: (caseId: string) => request<Kpis>(`/cases/${caseId}/kpis`),
    getExpiring: (caseId: string, q: { days?: string } = {}) => request<ExpiringResponse>(`/cases/${caseId}/expiring`, {}, q),
    getInventory: (caseId: string, q: { sort?: string; limit?: string } = {}) => request<InventoryResponse>(`/cases/${caseId}/inventory`, {}, q),
    getDeliveries: (caseId: string, q: { days?: string } = {}) => request<DeliveriesResponse>(`/cases/${caseId}/deliveries`, {}, q),
    getOutlook: (caseId: string, q: { days?: string } = {}) => request<Outlook>(`/cases/${caseId}/outlook`, {}, q),
    getOrderPlan: (caseId: string) => request<OrderPlan>(`/cases/${caseId}/order-plan`),
    listAlerts: (q: { store_id?: string; state?: string }) => request<AlertRecord[]>("/alerts", {}, q),
    /** Step 1 of a decision: turns (issue, option) into a pending proposal. Repeating the key returns the same proposal. */
    propose: (b: { case_id: string; issue_id: string; option_id: string; rationale?: string }, opts: { idempotencyKey?: string } = {}) =>
      request<Proposal>("/proposals", {
        ...send("POST", b),
        ...(opts.idempotencyKey ? { headers: { "Idempotency-Key": opts.idempotencyKey } } : {}),
      }),
    getDaySummary: (caseId: string, date?: string) =>
      request<DaySummary>(`/cases/${caseId}/day-summary`, {}, { date }),
    getForecast: (caseId: string, q: { sku?: string; from?: string; to?: string; level?: "sku" | "store" } = {}) =>
      request<ForecastResponse>(`/cases/${caseId}/forecast`, {}, q),
    /** Trace events: only the chat history fallback reads them. */
    getTrace: (storeId: string, caseId: string) =>
      request<TraceEvent[]>("/trace", {}, { store_id: storeId, case_id: caseId }),
  };
}

export type Api = ReturnType<typeof createApi>;

// A same-origin base ("") becomes the page origin. window.location.origin never carries
// embedded credentials, so the browser accepts the request even when the page was opened
// as https://user:pass@host (Firefox rejects relative fetches from such pages).
export function resolveBase(configured: string, origin: string): string {
  return configured === "" ? origin : configured;
}

// Dev: relative URLs go through the Vite proxy. Prod: VITE_API_URL or http://localhost:8080.
export const api: Api = createApi(
  resolveBase(
    import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "" : "http://localhost:8080"),
    typeof window === "undefined" ? "" : window.location.origin,
  ),
);
