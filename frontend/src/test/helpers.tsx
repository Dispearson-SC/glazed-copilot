import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import { ApiProvider } from "../ApiContext";
import { ApiError, type Api } from "../api";
import { SessionProvider } from "../SessionContext";
import { daySummaryA } from "./fixtures";
import type { Case, Proposal, Store, TraceEvent } from "../types";

export const store: Store = { store_id: "S030", name: "Glazed Centro", format: "mall", site_id: "X", region: "N",
  site_name: "Aeropuerto Norte", site_type: "Airport", display_name: "Aeropuerto Norte · Glazed Centro" };
export const store2: Store = { store_id: "S031", name: "Glazed Norte", format: "street", site_id: "Y", region: "N",
  site_name: "Plaza Sur", site_type: "Mall", display_name: "Plaza Sur · Glazed Norte" };

export const caseA: Case = {
  case_id: "c1", store_id: "S030", sim_today: "2026-03-01", mode: "live",
  parent_case_id: null, core_conversation_id: "conv1", title: "Caso uno", created_at: "2026-03-01T08:00:00Z",
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
    setOnUnauthorized: vi.fn(),
    getHealth: vi.fn(async () => ({})),
    me: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    login: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    getDemoUsers: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    demoLogin: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    logout: vi.fn(async () => ({})),
    listStores: vi.fn(async () => [store, store2]),
    listCases: vi.fn(async () => [caseA]),
    createCase: vi.fn(async () => caseA),
    advanceCase: vi.fn(async () => ({ sim_today: "2026-03-02", new_alerts: [], outcomes: [] })),
    sendMessage: vi.fn(async () => ({ turn_id: "t1" })),
    getTurn: vi.fn(async () => ({ turn_id: "t1", status: "done", reply: "listo" })),
    listProposals: vi.fn(async () => [proposalA]),
    decide: vi.fn(async () => ({})),
    propose: vi.fn(async () => ({ ...proposalA, proposal_id: "pp-new" })),
    listIssues: vi.fn(async () => []),
    getOrderPlan: vi.fn(async () => ({ store_id: "S030", as_of: "2026-03-01", total_lines: 0, lines: [] })),
    getExpiring: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    getInventory: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    getDeliveries: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    getOutlook: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    listAlerts: vi.fn(async () => []),
    getTrace: vi.fn(async () => []),
    getDaySummary: vi.fn(async (_id: string, date?: string) => ({ ...daySummaryA, date: date ?? daySummaryA.date })),
    getForecast: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    getPending: vi.fn(async () => ({ as_of: "2026-03-01", store_id: "S030", approvals: [], technical: [] })),
    getAnalysis: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    recordDecision: vi.fn(async () => ({ decision_id: "pp-new", proposal_id: "pp-new", status: "approved" })),
    getMemories: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    getTransferOptions: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    addNote: vi.fn(async () => ({ saved: true, memory_id: "note-x" })),
    getAgentsStatus: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    getInboxCounts: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
    listTurns: vi.fn(async () => { throw new ApiError(404, "Not Found"); }),
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
