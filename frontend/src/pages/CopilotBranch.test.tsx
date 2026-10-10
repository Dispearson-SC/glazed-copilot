import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  ayerSummary, branchDeliveries, branchExpiring, branchForecast, branchInventory, branchKpis, hoySummary, inventoryMany, inventoryWithStatus, metricForecasts, orderPlanA, outlookA, pendingA,
} from "../test/copilotFixtures";
import { caseA, fakeApi, renderPage } from "../test/helpers";
import CopilotPage from "./CopilotPage";

const julyCase = { ...caseA, sim_today: "2026-07-19" };
const api = (over = {}) =>
  fakeApi({
    listCases: async () => [julyCase],
    listProposals: async () => [],
    getPending: async () => pendingA,
    getOrderPlan: async () => orderPlanA,
    getForecast: vi.fn(async (_c: string, q: { metric?: keyof typeof metricForecasts } = {}) => (q.metric ? metricForecasts[q.metric] : branchForecast)),
    getOutlook: vi.fn(async () => outlookA),
    getDaySummary: vi.fn(async (_c: string, date?: string) => (date === "2026-07-18" ? ayerSummary : hoySummary)),
    getKpis: async () => branchKpis,
    getExpiring: async () => branchExpiring,
    getInventory: async () => branchInventory,
    getDeliveries: async () => branchDeliveries,
    ...over,
  });

async function openSucursal(a = api()) {
  renderPage(a, "/copiloto", "/copiloto", <CopilotPage />);
  await userEvent.click(await screen.findByRole("button", { name: /^Sucursal/ }));
  return a;
}

describe("Sucursal window", () => {
  it("opens on Hoy: expected sales and range, real sales pending, never today's actuals", async () => {
    const a = await openSucursal();
    expect(await screen.findByRole("heading", { name: "Hoy en la sucursal" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Hoy", selected: true })).toBeInTheDocument();
    expect(await screen.findByText("$868.54")).toBeInTheDocument();
    expect(screen.getByText("Rango probable $700 – $1,101")).toBeInTheDocument();
    expect(screen.getByText("Pendiente")).toBeInTheDocument();
    expect(screen.getByText("Se registra al cierre")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/1,135|1135/);
    expect(a.getForecast).toHaveBeenCalledWith("c1", { from: "2026-07-18", to: "2026-07-20", level: "store" });
  });

  it("asks the backend for yesterday's summary and today's calendar context", async () => {
    const a = await openSucursal();
    await screen.findByText("$868.54");
    expect(a.getDaySummary).toHaveBeenCalledWith("c1", "2026-07-18");
  });

  it("Ayer shows real sales against the same-weekday average, observed weather and visits", async () => {
    await openSucursal();
    await userEvent.click(await screen.findByRole("tab", { name: "Ayer" }));
    expect(await screen.findByRole("heading", { name: "Así cerró ayer" })).toBeInTheDocument();
    expect(screen.getByText("$849.20")).toBeInTheDocument();
    expect(screen.getByText("+25% vs promedio mismo día")).toBeInTheDocument();
    expect(screen.getByText("37° / 29°")).toBeInTheDocument();
    expect(screen.getByText("734")).toBeInTheDocument();
  });

  it("Mañana shows the forecast and 'Sin pronóstico' for the weather", async () => {
    await openSucursal();
    await userEvent.click(await screen.findByRole("tab", { name: "Mañana" }));
    expect(await screen.findByText("$833.39")).toBeInTheDocument();
    expect(screen.getAllByText("Sin pronóstico").length).toBeGreaterThan(0);
  });

  it("fills expected visits, orders, ticket and conversion for Hoy from the metric forecasts", async () => {
    const a = await openSucursal();
    await screen.findByText("$868.54");
    expect(screen.getByText("971")).toBeInTheDocument();
    expect(screen.getByText("85")).toBeInTheDocument();
    expect(screen.getByText("$9.56")).toBeInTheDocument();
    expect(screen.getByText("8.7%")).toBeInTheDocument();
    expect(a.getForecast).toHaveBeenCalledWith("c1", { metric: "footfall", from: "2026-07-18", to: "2026-07-20", level: "store" });
    expect(a.getOutlook).toHaveBeenCalledWith("c1", { days: "2" });
  });

  it("says 'Disponible pronto' for those figures while the routes answer 404", async () => {
    const { ApiError } = await import("../api");
    const nf = async () => { throw new ApiError(404, "Not Found"); };
    await openSucursal(api({ getOutlook: nf, getForecast: vi.fn(async (_c: string, q: { metric?: string } = {}) => { if (q.metric) throw new ApiError(404, "Not Found"); return branchForecast; }) }));
    await screen.findByText("$868.54");
    expect(screen.getAllByText("Disponible pronto").length).toBeGreaterThanOrEqual(3);
  });

  it("renders empty values small and muted, never as a headline figure", async () => {
    const { ApiError } = await import("../api");
    await openSucursal(api({ getOutlook: async () => { throw new ApiError(404, "Not Found"); }, getForecast: vi.fn(async (_c: string, q: { metric?: string } = {}) => { if (q.metric) throw new ApiError(404, "Not Found"); return branchForecast; }) }));
    await screen.findByText("$868.54");
    for (const el of screen.getAllByText("Disponible pronto")) expect(el.className).toMatch(/text-\[13px\]/);
  });

  it("shows the backend status pill, reason, forecast outflow and scheduled delivery per inventory row", async () => {
    await openSucursal(api({ getInventory: async () => inventoryWithStatus }));
    const row = (await screen.findByText("Better For You Breakfast Sandwich")).closest("div[data-row]") as HTMLElement;
    expect(within(row).getByText("Crítico")).toBeInTheDocument();
    expect(within(row).getByText("Crítico")).toHaveAttribute("title", expect.stringContaining("se agota antes de la próxima entrega"));
    expect(within(row).getByText("51.31 en 3 días")).toBeInTheDocument();
    expect(within(row).getByText("+40 · llega lun 20")).toBeInTheDocument();
  });

  it("shows the closing sentence next to the stock and expands from 10 to the full list", async () => {
    await openSucursal(api({ getInventory: async () => inventoryMany }));
    const first = (await screen.findByText("Producto 1")).closest("div[data-row]") as HTMLElement;
    expect(within(first).getByText("Agotado hoy (6.9 h sin stock) · llegan 40 mañana")).toBeInTheDocument();
    expect(document.querySelectorAll("div[data-row]")).toHaveLength(10);
    await userEvent.click(screen.getByRole("button", { name: "Ver todo (12)" }));
    expect(document.querySelectorAll("div[data-row]")).toHaveLength(12);
    await userEvent.click(screen.getByRole("button", { name: "Ver menos" }));
    expect(document.querySelectorAll("div[data-row]")).toHaveLength(10);
  });

  it("lists inventory with stock, daily outflow and the order-plan purchase", async () => {
    await openSucursal();
    const row = (await screen.findByText("Md Choc Stout C.B. Wsweet Cold Foam")).closest("div[data-row]") as HTMLElement;
    expect(within(row).getByText("1.5 días de cobertura")).toBeInTheDocument();
    expect(within(row).getByText("3.23 /día")).toBeInTheDocument();
    expect(within(row).getByText("+10 · llega mar 21")).toBeInTheDocument();
  });

  it("lists the placed orders on the way, late first", async () => {
    await openSucursal();
    expect(await screen.findByText("Vasos 12 oz · 40")).toBeInTheDocument();
    expect(screen.getByText("Atrasado")).toBeInTheDocument();
    expect(screen.getByText("Pioneer Merch & Packaging · jue 16")).toBeInTheDocument();
  });

  it("the button at the bottom goes to Decisiones with the pending count", async () => {
    await openSucursal();
    const btn = await screen.findByRole("button", { name: /compras? esperan? tu decisión/ });
    expect(btn).toHaveTextContent("1 compras esperan tu decisión".replace("1 compras esperan", "1 compra espera"));
    await userEvent.click(btn);
    expect(await screen.findByRole("heading", { name: "Decisiones de hoy" })).toBeInTheDocument();
  });

  it("degrades to 'Sin datos' when a source fails, without hiding the rest", async () => {
    await openSucursal(api({ getInventory: async () => { throw new Error("boom"); } }));
    expect(await screen.findByText("$868.54")).toBeInTheDocument();
    expect(screen.getByText("Sin datos de inventario")).toBeInTheDocument();
  });
});
