import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  agentsA, alertsA, ayerSummary, branchDeliveries, branchExpiring, branchForecast, branchKpis, hoySummary, integrityA, inventoryWithStatus, memoriesA, metricForecasts, orderPlanA, outlookA, pendingA,
} from "./test/copilotFixtures";
import { caseA, fakeApi, renderPage } from "./test/helpers";
import DashboardPage from "./pages/DashboardPage";
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
    getKpis: async () => branchKpis,
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
  it("bottom nav: no dead links; Pedidos, Productos and Ajustes open copilot windows", async () => {
    renderPage(fakeApi(), "/", "/", <DashboardPage />);
    const nav = await screen.findByRole("navigation", { name: "Navegación principal" });
    const hrefs = Object.fromEntries(within(nav).getAllByRole("link").map((a) => [a.textContent?.replace(/^[a-z_]+/, ""), a.getAttribute("href")]));
    expect(hrefs).toEqual({
      Resumen: "/",
      Pedidos: "/copiloto?tab=decisiones",
      Productos: "/copiloto?tab=sucursal",
      Chat: "/chat",
      Ajustes: "/copiloto?tab=alertas",
    });
  });

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

  it("the copilot logo goes back to Resumen", async () => {
    renderPage(copilotApi(), "/copiloto", "/copiloto", <CopilotPage />);
    expect(await screen.findByRole("link", { name: /Volver al resumen/ })).toHaveAttribute("href", "/");
  });
});
