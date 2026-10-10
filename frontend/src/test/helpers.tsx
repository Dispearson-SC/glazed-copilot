import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import { ApiProvider } from "../ApiContext";
import { ApiError, type Api } from "../api";
import { SessionProvider } from "../SessionContext";
import { briefingA, daySummaryA, issueA, kpisA, planA } from "./fixtures";
import type { Alert, Case, Proposal, Store, TraceEvent } from "../types";

export const store: Store = { store_id: "S030", name: "Glazed Centro", format: "mall", site_id: "X", region: "N",
  site_name: "Aeropuerto Norte", site_type: "Airport", display_name: "Aeropuerto Norte · Glazed Centro" };
export const store2: Store = { store_id: "S031", name: "Glazed Norte", format: "street", site_id: "Y", region: "N",
  site_name: "Plaza Sur", site_type: "Mall", display_name: "Plaza Sur · Glazed Norte" };

export const caseA: Case = {
  case_id: "c1", store_id: "S030", sim_today: "2026-03-01", mode: "live",
  parent_case_id: null, core_conversation_id: "conv1", title: "Caso uno", created_at: "2026-03-01T08:00:00Z",
};

export const alertA: Alert = {
  alert_id: "a1", alert_type: 2, store_id: "S030", case_id: "c1", severity_usd: 123.5, state: "nueva",
  issue: { kind: "stockout_risk", sku: "DONUT-GLZ" }, issue_key: "k1", as_of: "2026-03-01",
  created_at: "2026-03-01T08:00:00Z",
};

export const proposalA: Proposal = {
  proposal_id: "p1", case_id: "c1", store_id: "S030", issue_id: "a1", action_type: "place_order",
  params: { qty: 40 }, tier: "N2", rationale: "Evitar quiebre", status: "pending", reason: "",
  agent_id: "supply", created_at: "2026-03-01T08:01:00Z",
};

export function ev(ts: string, from: string, to: string, kind: TraceEvent["kind"] = "message", payload = {}): TraceEvent {
  return { case_id: "c1", store_id: "S030", ts, from_agent: from, to_agent: to, kind, payload };
}

export function fakeApi(over: Partial<Record<keyof Api, unknown>> = {}): Api {
  const base = {
    health: vi.fn(async () => ({ status: "ok" })),
    listStores: vi.fn(async () => [store, store2]),
    listCases: vi.fn(async () => [caseA]),
    createCase: vi.fn(async () => caseA),
    forkCase: vi.fn(async () => ({ ...caseA, case_id: "c2", parent_case_id: "c1" })),
    sendMessage: vi.fn(async () => ({ turn_id: "t1" })),
    getTurn: vi.fn(async () => ({ turn_id: "t1", status: "done", reply: "listo" })),
    listAlerts: vi.fn(async () => [alertA]),
    setAlertState: vi.fn(async () => ({ ...alertA, state: "vista" })),
    listProposals: vi.fn(async () => [proposalA]),
    decide: vi.fn(async () => ({})),
    getTrace: vi.fn(async () => []),
    getCase: vi.fn(async () => caseA),
    advance: vi.fn(async () => ({ sim_today: "2026-03-02", new_alerts: [] })),
    getOrderPlan: vi.fn(async () => planA),
    getDaySummary: vi.fn(async (_id: string, date?: string) => ({ ...daySummaryA, date: date ?? daySummaryA.date })),
    getBriefing: vi.fn(async () => briefingA),
    getKpis: vi.fn(async () => kpisA),
    getCompliance: vi.fn(async () => []),
    inject: vi.fn(async () => ({})),
    getForecast: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    getForecastAccuracy: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    listTurns: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    getDecisions: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    proposeOption: vi.fn(async () => ({ ...proposalA, proposal_id: "p9", issue_id: issueA.issue_id })),
  };
  return { ...base, ...over } as unknown as Api;
}

export function renderPage(api: Api, path: string, routePattern: string, element: React.ReactElement) {
  return render(
    <ApiProvider api={api}>
      <SessionProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path={routePattern} element={element} />
          </Routes>
        </MemoryRouter>
      </SessionProvider>
    </ApiProvider>,
  );
}
