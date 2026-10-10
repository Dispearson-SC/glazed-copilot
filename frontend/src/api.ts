import type { AdvanceResult, Alert, Briefing, Case, CaseMode, ComplianceRecord, DaySummary, Execution, InjectBody, Kpis, OrderPlan, Proposal, Store, TraceEvent, Turn } from "./types";

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

export function createApi(baseUrl: string, fetchFn: typeof fetch = (...a) => fetch(...a)) {
  const base = baseUrl.replace(/\/$/, "");

  async function request<T>(path: string, init: RequestInit = {}, query?: Query): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (init.body !== undefined) headers["Content-Type"] = "application/json";
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
    health: () => request<{ status: string }>("/health"),
    listStores: () => request<Store[]>("/stores"),
    listCases: (query: { store_id?: string }) => request<Case[]>("/cases", {}, query),
    createCase: (b: { store_id: string; sim_today: string; mode?: CaseMode; title?: string }) =>
      request<Case>("/cases", send("POST", b)),
    forkCase: (caseId: string, b: { title?: string } = {}) =>
      request<Case>(`/cases/${caseId}/fork`, send("POST", b)),
    sendMessage: (caseId: string, text: string) =>
      request<{ turn_id: string }>(`/cases/${caseId}/messages`, send("POST", { text })),
    getTurn: (caseId: string, turnId: string) => request<Turn>(`/cases/${caseId}/turns/${turnId}`),
    listAlerts: (query: { store_id?: string; state?: string }) => request<Alert[]>("/alerts", {}, query),
    setAlertState: (alertId: string, state: string) =>
      request<Alert>(`/alerts/${alertId}`, send("PATCH", { state })),
    listProposals: (query: { case_id?: string; status?: string }) =>
      request<Proposal[]>("/proposals", {}, query),
    decide: (proposalId: string, b: { approved: boolean; reason?: string }) =>
      request<Execution>(`/proposals/${proposalId}/decision`, send("POST", b)),
    getCase: (caseId: string) => request<Case>(`/cases/${caseId}`),
    getDaySummary: (caseId: string, date?: string) =>
      request<DaySummary>(`/cases/${caseId}/day-summary`, {}, { date }),
    getBriefing: (caseId: string) => request<Briefing>(`/cases/${caseId}/briefing`),
    advance: (caseId: string, days = 1) => request<AdvanceResult>(`/cases/${caseId}/advance`, send("POST", { days })),
    // REQUIRED backend routes (not in the public API yet).
    getOrderPlan: (caseId: string) => request<OrderPlan>(`/cases/${caseId}/order-plan`),
    getKpis: (caseId: string) => request<Kpis>(`/cases/${caseId}/kpis`),
    proposeOption: (b: { case_id: string; issue_id: string; option_id: string; rationale: string }) =>
      request<Proposal>("/proposals", send("POST", b)),
    getCompliance: (caseId: string) => request<ComplianceRecord[]>(`/cases/${caseId}/compliance`),
    inject: (caseId: string, b: InjectBody) => request<unknown>(`/cases/${caseId}/inject`, send("POST", b)),
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
