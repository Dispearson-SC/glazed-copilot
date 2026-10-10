import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  agentsA, alertsA, ayerSummary, branchDeliveries, branchExpiring, branchForecast, branchKpis, hoySummary, integrityA, inventoryWithStatus, memoriesA, metricForecasts, orderPlanA, outlookA, pendingA,
} from "./test/copilotFixtures";
import { caseA, fakeApi, renderPage } from "./test/helpers";
import App from "./App";
import { ApiProvider } from "./ApiContext";
import { SessionProvider } from "./SessionContext";
import { MemoryRouter } from "react-router-dom";
import CopilotPage from "./pages/CopilotPage";

const copilotApi = () =>
  fakeApi({
    listCases: async () => [{ ...caseA, sim_today: "2026-07-19" }],
    listProposals: async () => [],
    getPending: async () => pendingA,
    getOrderPlan: async () => orderPlanA,
    getForecast: vi.fn(async (_c: string, q: { metric?: keyof typeof metricForecasts } = {}) => (q.metric ? metricForecasts[q.metric] : branchForecast)),
    getOutlook: async () => outlookA,
    getDaySummary: async (_c: string, date?: string) => (date === "2026-07-18" ? ayerSummary : hoySummary),
    getExpiring: async () => branchExpiring,
    getInventory: async () => inventoryWithStatus,
    getDeliveries: async () => branchDeliveries,
    getMemories: async () => memoriesA,
    listAlerts: async () => alertsA,
    listIssues: async () => integrityA,
    getAgentsStatus: async () => ({ connected: true, agents: agentsA }),
    getAnalysis: async () => { throw new Error("no"); },
  });

describe("navigation reaches every screen", () => {
  it.each([
    ["decisiones", "Decisiones de hoy"],
    ["alertas", "Advertencias"],
  ])("/copiloto?tab=%s opens that window", async (tab, heading) => {
    renderPage(copilotApi(), `/copiloto?tab=${tab}`, "/copiloto", <CopilotPage />);
    expect(await screen.findByRole("heading", { name: new RegExp(heading) })).toBeInTheDocument();
  });

  it("/copiloto?tab=sucursal opens the Sucursal window", async () => {
    renderPage(copilotApi(), "/copiloto?tab=sucursal", "/copiloto", <CopilotPage />);
    const capsule = await screen.findByRole("navigation", { name: /copiloto/i });
    expect(within(capsule).getByRole("button", { name: /Sucursal/ })).toHaveAttribute("aria-current", "page");
  });

  it("an unknown tab falls back to Agente", async () => {
    renderPage(copilotApi(), "/copiloto?tab=nope", "/copiloto", <CopilotPage />);
    const capsule = await screen.findByRole("navigation", { name: /copiloto/i });
    expect(within(capsule).getByRole("button", { name: /Agente/ })).toHaveAttribute("aria-current", "page");
  });

  it("the copilot logo is a plain image, not a link", async () => {
    renderPage(copilotApi(), "/copiloto", "/copiloto", <CopilotPage />);
    expect(await screen.findByAltText("Logo Glazed Co.")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });
});

describe("the app is the Copiloto only", () => {
  const open = (path: string) =>
    render(
      <ApiProvider api={copilotApi()}>
        <SessionProvider>
          <MemoryRouter initialEntries={[path]}>
            <App />
          </MemoryRouter>
        </SessionProvider>
      </ApiProvider>,
    );

  it.each(["/", "/resumen", "/login", "/chat", "/nope/never"])("%s redirects to /copiloto", async (path) => {
    open(path);
    expect(await screen.findByRole("navigation", { name: /copiloto/i })).toBeInTheDocument();
  });

  it("keeps ?tab= working", async () => {
    open("/copiloto?tab=alertas");
    expect(await screen.findByRole("heading", { name: /Advertencias/ })).toBeInTheDocument();
  });

  it("has no Resumen, Iniciar sesión, bottom navigation or floating chat", async () => {
    open("/resumen");
    await screen.findByRole("navigation", { name: /copiloto/i });
    expect(screen.queryByText("Resumen")).toBeNull();
    expect(screen.queryByLabelText("Iniciar sesión")).toBeNull();
    expect(screen.queryByRole("navigation", { name: "Navegación principal" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Abrir chat|Cerrar chat/ })).toBeNull();
  });
});
