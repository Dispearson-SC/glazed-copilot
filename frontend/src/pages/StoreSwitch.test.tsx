import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { agentsA } from "../test/copilotFixtures";
import { caseA, fakeApi, renderPage, store } from "../test/helpers";
import CopilotPage from "./CopilotPage";

// Two stores whose every answer carries a marker, so a leftover from the previous store is detectable in any window.
const stores = [
  { ...store, store_id: "S001", display_name: "Tienda Alfa" },
  { ...store, store_id: "S005", display_name: "Tienda Beta" },
];
const cases = {
  S001: { ...caseA, case_id: "cA1", store_id: "S001", sim_today: "2026-07-19" },
  S005: { ...caseA, case_id: "cB1", store_id: "S005", sim_today: "2026-07-19" },
};
const mark = (caseId: string) => (caseId === "cA1" ? "ALFA" : "BETA");

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((r) => (resolve = r));
  return { promise, resolve };
}

function storeApi(gates: Record<string, Promise<void>>) {
  const later = async <T,>(caseId: string, v: T): Promise<T> => {
    await (gates[caseId] ?? Promise.resolve());
    return v;
  };
  return fakeApi({
    listStores: async () => stores,
    listCases: vi.fn(async (q: { store_id?: string }) => [cases[q.store_id as keyof typeof cases]]),
    listProposals: async () => [],
    getAgentsStatus: async () => ({ connected: true, agents: agentsA }),
    getPending: vi.fn((c: string) =>
      later(c, {
        as_of: "2026-07-19", store_id: c,
        approvals: [{
          issue_id: `${c}|overstock|1`, title: "t", tier: "N2", deadline: "2026-07-19", impact_usd: { low: 1, mid: 1, high: 1 }, confidence: { score: 0.5, calibrated: true },
          problem: `Problema ${mark(c)}`, recommendation: { option_id: "o1", label: `Omitir pedido ${mark(c)}`, action_type: "skip_order", params: {} }, requires_approval: true,
        }],
        technical: [],
      } as never),
    ),
    getInboxCounts: vi.fn((c: string) => later(c, { approvals: c === "cA1" ? 41 : 2, technical: 0, alerts: c === "cA1" ? 37 : 1 })),
    getInventory: vi.fn((c: string) =>
      later(c, { as_of: "2026-07-19", items: [{ sku: "S1", product_name: `Inv ${mark(c)}`, on_hand: 3, avg_daily_demand: 1, days_of_cover: 3, display_status_es: `Estado ${mark(c)}` }] } as never),
    ),
    getMemories: vi.fn((c: string) =>
      later(c, [{ memory_id: "m1", category: "demanda", text: `Memoria ${mark(c)}`, source: "gerente", cases_count: 1, verified: true, created_at: "2026-07-19T00:00:00Z", new: false }] as never),
    ),
    listAlerts: vi.fn((q: { store_id?: string }) => {
      const c = cases[q.store_id as keyof typeof cases].case_id;
      return later(c, [{ alert_id: `al-${c}`, alert_type: 1, store_id: q.store_id, case_id: c, severity_usd: 5, state: "nueva", as_of: "2026-07-19", category: "operacion", agent_id: "present", ts: "2026-07-19T07:00:00Z", title_es: `Alerta ${mark(c)}`, issue: { kind: "overstock_waste", product_name: `Prod ${mark(c)}` } }] as never);
    }),
    listTurns: vi.fn((c: string) => later(c, [{ turn_id: `t-${c}`, ts: "2026-07-19T08:00:00Z", user_text: `Chat ${mark(c)}`, reply: `Respuesta ${mark(c)}`, status: "done" }] as never)),
  });
}

const tabs = ["Agente", "Decisiones", "Sucursal", "Memorias", "Alertas"];
const visit = async (name: string) => userEvent.click(screen.getByRole("button", { name: new RegExp(`^${name}`) }));
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 60)); });

async function switchToBeta() {
  await userEvent.click(screen.getByRole("button", { name: /cambiar sucursal/i }));
  await userEvent.click(await screen.findByRole("button", { name: /Tienda Beta/ }));
}

async function expectNo(marker: string) {
  for (const t of tabs) {
    await visit(t);
    await flush();
    expect(document.body.textContent).not.toContain(marker);
  }
  expect(screen.queryByText("41")).toBeNull();
  expect(screen.queryByText("37")).toBeNull();
}

beforeEach(() => localStorage.setItem("glazed.storeId", "S001"));

// Heavy multi-window scenario: give it room when the machine is loaded.
describe("switching stores never shows the previous store's data", { timeout: 20_000 }, () => {
  it("S001 answers that resolve AFTER the switch to S005 are ignored in every window", async () => {
    const alfa = deferred();
    renderPage(storeApi({ cA1: alfa.promise }), "/copiloto", "/copiloto", <CopilotPage />);
    await screen.findByRole("navigation", { name: /copiloto/i });
    await flush();
    await switchToBeta();
    await visit("Decisiones");
    expect(await screen.findByText(/Omitir pedido BETA/)).toBeInTheDocument();
    await act(async () => { alfa.resolve(); });
    await flush();
    await expectNo("ALFA");
    await visit("Memorias");
    expect(await screen.findByText(/Memoria BETA/)).toBeInTheDocument();
    await visit("Alertas");
    expect(await screen.findByText(/Alerta BETA/)).toBeInTheDocument();
  });

  it("S001 data already on screen disappears while S005 is still loading, in every window", async () => {
    const beta = deferred();
    renderPage(storeApi({ cB1: beta.promise }), "/copiloto", "/copiloto", <CopilotPage />);
    await visit("Decisiones");
    expect(await screen.findByText(/Omitir pedido ALFA/)).toBeInTheDocument();
    await visit("Sucursal");
    expect(await screen.findByText(/Inv ALFA/)).toBeInTheDocument();
    await visit("Agente");
    expect(await screen.findByText(/Chat ALFA/)).toBeInTheDocument();
    await switchToBeta();
    await waitFor(() => expect(screen.queryByText(/Chat ALFA/)).toBeNull());
    await expectNo("ALFA");
    await act(async () => { beta.resolve(); });
    await visit("Sucursal");
    expect(await screen.findByText(/Inv BETA/)).toBeInTheDocument();
    await visit("Agente");
    expect(await screen.findByText(/Chat BETA/)).toBeInTheDocument();
  });
});
