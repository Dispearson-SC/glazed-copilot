import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  agentsA, alertsA, ayerSummary, branchDeliveries, branchExpiring, branchForecast, branchKpis, hoySummary, integrityA, inventoryWithStatus, memoriesA, metricForecasts, orderPlanA, outlookA, pendingA,
} from "../test/copilotFixtures";
import { caseA, fakeApi, renderPage } from "../test/helpers";
import CopilotPage from "./CopilotPage";

const api = (over = {}) =>
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
    ...over,
  });

const open = async (tab?: RegExp, a = api()) => {
  renderPage(a, "/copiloto", "/copiloto", <CopilotPage />);
  if (tab) await userEvent.click(await screen.findByRole("button", { name: tab }));
  return a;
};

/** Copiloto.dc.html, window by window. */
describe("Copiloto (/copiloto) matches Copiloto.dc.html", () => {
  it("top bar: logo, 'Glazed Co.', 'Copiloto · Sucursal S030' and the Ajustes button", async () => {
    await open();
    const bar = await screen.findByRole("banner");
    expect(within(bar).getByRole("img", { name: "Logo Glazed Co." })).toBeInTheDocument();
    expect(within(bar).getByText("Glazed Co.")).toBeInTheDocument();
    expect(await within(bar).findByText("Copiloto · Sucursal S030")).toBeInTheDocument();
    expect(within(bar).getByRole("button", { name: "Ajustes del copiloto" })).toBeInTheDocument();
  });

  it("capsule: exactly Agente, Decisiones, Sucursal, Memorias, Alertas", async () => {
    await open();
    const nav = await screen.findByRole("navigation", { name: "Ventanas del copiloto" });
    expect(within(nav).getAllByRole("button").map((b) => b.textContent?.replace(/\d+$/, ""))).toEqual(["forumAgente", "fact_checkDecisiones", "storefrontSucursal", "psychologyMemorias", "warningAlertas"]);
  });

  it("Agente: orb status with agents, title, pending line, three suggestions, composer with mic", async () => {
    await open();
    expect(await screen.findByText("Listo · 2 agentes conectados")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "¿Qué decidimos hoy?" })).toBeInTheDocument();
    expect(await screen.findByText("1 esperan tu opinión · 1 listas para aceptar")).toBeInTheDocument();
    for (const c of ["¿Qué pido hoy?", "¿Por qué tiramos tanta dona?", "Resume las advertencias"]) expect(screen.getByRole("button", { name: c })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hablar con el copiloto" })).toBeInTheDocument();
    expect(screen.getByLabelText("Mensaje para el copiloto")).toHaveAttribute("placeholder", "Pregunta o decide algo…");
  });

  it("Decisiones: date, title, subtitle, both sections, counts and the resolved line", async () => {
    await open(/^Decisiones/);
    expect(await screen.findByText("Domingo 19 de julio")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Decisiones de hoy" })).toBeInTheDocument();
    expect(screen.getByText("El código calcula; el copiloto explica. Tú decides.")).toBeInTheDocument();
    expect(screen.getByText("Casos difíciles: analízalos con el copiloto")).toBeInTheDocument();
    expect(screen.getByText("Listas para aceptar · cantidades y fechas calculadas")).toBeInTheDocument();
    expect(await screen.findByText("0 decisiones automáticas (N1) ya colocadas hoy")).toBeInTheDocument();
  });

  it("Decisiones: the resolved line adds the decisions accepted by the manager", async () => {
    const a = await open(/^Decisiones/);
    await userEvent.click(await screen.findByRole("button", { name: /Aceptar/ }));
    expect(await screen.findByText("0 decisiones automáticas (N1) ya colocadas hoy · 1 aceptada por ti")).toBeInTheDocument();
    expect(a.recordDecision).toHaveBeenCalled();
  });

  it("Sucursal: header with the store code, tabs, expected/real cards, weather, context, tiles and ranges", async () => {
    await open(/^Sucursal/);
    expect(await screen.findByText("Sucursal S030")).toBeInTheDocument();
    expect(screen.getByRole("tablist", { name: "Día" })).toBeInTheDocument();
    for (const t of ["Ayer", "Hoy", "Mañana"]) expect(screen.getByRole("tab", { name: t })).toBeInTheDocument();
    for (const l of ["Ventas esperadas", "Ventas reales", "Contexto del día", "visitas esperadas", "Pedidos esperados", "Ticket promedio", "Conversión", "Merma esperada", "Venta perdida esperada"]) expect(screen.getAllByText(l).length).toBeGreaterThan(0);
    expect(screen.getByText("Pronóstico Sin datos")).toBeInTheDocument();
    expect(screen.getByText(/^Clima ·/)).toBeInTheDocument();
  });

  it("Sucursal: the lost-sales figure is the served range, with 'por falta de producto' under it", async () => {
    await open(/^Sucursal/);
    await userEvent.click(await screen.findByRole("tab", { name: "Mañana" }));
    expect(await screen.findByText("$0 – $105")).toBeInTheDocument();
    expect(screen.getAllByText("por falta de producto").length).toBeGreaterThan(0);
  });

  it("Sucursal: inventory section with its subtitle, 'Proyección desde hoy' chip, Actual/Salida/Compra and the status pill", async () => {
    await open(/^Sucursal/);
    expect(await screen.findByRole("heading", { name: "Inventario y salida" })).toBeInTheDocument();
    expect(screen.getByText("Actual · salida pronosticada hoy · programado")).toBeInTheDocument();
    expect(screen.getByText("Proyección desde hoy")).toBeInTheDocument();
    const row = (await screen.findByText("Better For You Breakfast Sandwich")).closest("div[data-row]") as HTMLElement;
    for (const l of ["Actual", "Salida", "Compra"]) expect(within(row).getByText(l)).toBeInTheDocument();
    expect(within(row).getByText("Crítico")).toBeInTheDocument();
  });

  it("Sucursal: 'Programados para compra' and the button to Decisiones", async () => {
    await open(/^Sucursal/);
    expect(await screen.findByRole("heading", { name: "Programados para compra" })).toBeInTheDocument();
    expect(screen.getByText("Pedidos colocados y en camino")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /compra espera tu decisión/ })).toBeInTheDocument();
  });

  it("Memorias: header with the store code, search, five filters, cards and the footnote", async () => {
    await open(/^Memorias/);
    expect(await screen.findByText("Poco a poco · S030")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Memorias técnicas" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Buscar una memoria" })).toHaveAttribute("placeholder", "Busca una memoria");
    for (const f of ["Todas", "Proveedores", "Demanda", "Eventos", "Preferencias"]) expect(screen.getByRole("button", { name: f })).toBeInTheDocument();
    expect(screen.getByText(/Las memorias se escriben solo después de una decisión/)).toBeInTheDocument();
  });

  it("Alertas: header, four filters and cards with tone, time, agent and Preguntar (no Revertir)", async () => {
    await open(/^Alertas/);
    expect(await screen.findByText("Centinela · Auditor · Abastecimiento")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Advertencias" })).toBeInTheDocument();
    expect(screen.getByText("Todo lo que el sistema detectó, ordenado por impacto en dinero.")).toBeInTheDocument();
    for (const f of ["Todas", "Operación", "Datos e integridad", "Automáticas"]) expect(screen.getByRole("button", { name: f })).toBeInTheDocument();
    expect((await screen.findAllByRole("button", { name: /Preguntar/ })).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Revertir" })).toBeNull();
  });

  it("Alertas: an alert without a known agent says 'Sin datos' instead of inventing one", async () => {
    await open(/^Alertas/, api({ getAgentsStatus: async () => { throw new Error("nf"); } }));
    expect((await screen.findAllByText("Sin datos")).length).toBeGreaterThan(0);
    expect(screen.queryByText("Agente no informado")).toBeNull();
  });

  it("Reject sheet and toast keep the design's texts", async () => {
    await open(/^Decisiones/);
    const card = (await screen.findByRole("heading", { name: /Pedir 10 unidades/ })).closest("article")!;
    await userEvent.click(within(card).getByRole("button", { name: /Rechazar/ }));
    const sheet = screen.getByRole("dialog", { name: "Motivo del rechazo" });
    expect(within(sheet).getByText("Rechazar decisión")).toBeInTheDocument();
    expect(within(sheet).getByRole("heading", { name: "¿Por qué la rechazas?" })).toBeInTheDocument();
    for (const r of ["Precio o costo", "Desconfío del dato", "Falta personal", "Mal momento", "Prefiero no quedarme corto", "Otro"]) expect(within(sheet).getByRole("button", { name: r })).toBeInTheDocument();
    expect(within(sheet).getByLabelText("Cuéntale más (opcional)")).toBeInTheDocument();
    expect(within(sheet).getByRole("button", { name: "Enviar motivo y rechazar" })).toBeDisabled();
  });

  it("has none of the legacy elements", async () => {
    await open(/^Sucursal/);
    await screen.findByText("Sucursal S030");
    for (const legacy of [/Promedio mismo día/, /Algunos datos no cargaron/, /Merma real/, /Venta perdida \(7 días\)/, /Agente no informado/, /Nuevo aprendizaje/]) {
      expect(screen.queryByText(legacy)).toBeNull();
    }
  });
});
