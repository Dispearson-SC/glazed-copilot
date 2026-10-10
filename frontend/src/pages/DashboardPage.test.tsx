import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api";
import { daySummaryA } from "../test/fixtures";
import { fakeApi, renderPage } from "../test/helpers";
import type { ForecastResponse } from "../types";
import DashboardPage from "./DashboardPage";

const open = (api = fakeApi()) => renderPage(api, "/", "/", <DashboardPage />);

const forecastFor = (over: Partial<ForecastResponse> = {}): ForecastResponse => {
  const days = Array.from({ length: 10 }, (_, i) => `2026-03-${String(2 + i).padStart(2, "0")}`);
  return {
    store_id: "S030", sku: null, level: "store", as_of: "2026-03-01", forecast_origin: "2026-03-01",
    model: "glm_poisson", model_version: "1", unit: "USD", horizon_days: 7,
    points: days.map((date, i) => ({
      date, forecast: 100 + i, p10: 80, p90: 120, baseline: 90, actual: null, censored: false,
    })),
    metrics_to_date: { wape: 0.298, bias: 0, coverage_p10_p90: 0.88, wape_baseline: 0.357, n_days: 28 },
    ...over,
  };
};

describe("DashboardPage header", () => {
  it("shows the title, the long date of the simulated today and the simulated clock", async () => {
    open();
    expect(await screen.findByRole("heading", { name: "Resumen de hoy" })).toBeInTheDocument();
    expect(screen.getByText("domingo, 1 de marzo de 2026")).toBeInTheDocument();
    expect(screen.getByText("Fecha simulada")).toBeInTheDocument();
    expect(screen.getByTestId("sim-today")).toHaveTextContent("2026-03-01");
  });

  it("shows an empty state without a case", async () => {
    open(fakeApi({ listCases: async () => [] }));
    expect(await screen.findByText("Sin caso activo para esta sucursal")).toBeInTheDocument();
  });

  it("shows an error, not 'Sin datos', when the day-summary request fails", async () => {
    open(fakeApi({ getDaySummary: async () => { throw new Error("fecha posterior a as_of"); } }));
    expect(await screen.findByText(/fecha posterior a as_of/)).toBeInTheDocument();
    expect(screen.queryByText("Sin datos")).toBeNull();
  });
});

describe("DashboardPage hero and metrics", () => {
  it("shows net sales, the delta and progress against the same-weekday average", async () => {
    open();
    const hero = await screen.findByTestId("hero");
    expect(await within(hero).findByText("$733.91")).toBeInTheDocument();
    expect(within(hero).getByText("Ventas de hoy")).toBeInTheDocument();
    expect(screen.getByTestId("hero-delta")).toHaveTextContent("+19% vs promedio");
    expect(hero).toHaveTextContent("Promedio mismo día (8 sem): $617.92");
    expect(screen.getByTestId("hero-progress")).toHaveTextContent("119% del promedio");
    expect(screen.getByTestId("hero-bar")).toHaveStyle({ width: "100%" });
  });

  it("puts the delta pill on the amount row, to its right, with the short text", async () => {
    open();
    const pill = await screen.findByTestId("hero-delta");
    expect(pill).toHaveTextContent(/^north_east\+19% vs promedio$/);
    const row = pill.parentElement!;
    expect(row.className).toContain("justify-between");
    expect(row.firstElementChild).toHaveTextContent("$733.91");
    expect(row.lastElementChild).toBe(pill);
  });

  it("labels the metric cards as in the design", async () => {
    open();
    await screen.findByTestId("metric-transactions");
    expect(screen.getByTestId("metric-transactions")).toHaveTextContent("Pedidos realizados");
    expect(screen.getByTestId("metric-avg-ticket")).toHaveTextContent("Ticket promedio");
    expect(screen.getByTestId("metric-units")).toHaveTextContent("Items vendidos");
  });

  it("caps the bar below the average and uses the weeks reported by the backend", async () => {
    open(fakeApi({
      getDaySummary: async () => ({ ...daySummaryA, totals: { ...daySummaryA.totals, net_sales: 308.96 }, vs_same_weekday_avg: { baseline_net_sales: 617.92, weeks_used: 7, delta_pct: -50 } }),
    }));
    expect(await screen.findByTestId("hero-progress")).toHaveTextContent("50% del promedio");
    expect(screen.getByTestId("hero")).toHaveTextContent("(7 sem)");
    expect(screen.getByTestId("hero-bar")).toHaveStyle({ width: "50%" });
    expect(screen.getByTestId("hero-delta")).toHaveTextContent("-50% vs promedio");
  });

  it("maps transactions, average ticket and units, without staff hours", async () => {
    open();
    expect(await screen.findByTestId("metric-transactions")).toHaveTextContent("74");
    expect(screen.getByTestId("metric-avg-ticket")).toHaveTextContent("$9.92");
    expect(screen.getByTestId("metric-units")).toHaveTextContent("138");
    expect(screen.queryByText(/36\.2/)).toBeNull();
  });

  it("guards the average ticket when there are no transactions", async () => {
    open(fakeApi({ getDaySummary: async () => ({ ...daySummaryA, totals: { ...daySummaryA.totals, transactions: 0 } }) }));
    expect(await screen.findByTestId("metric-avg-ticket")).toHaveTextContent("—");
  });

  it("shows 'Sin datos' (not zero) when totals is null, with no delta and no goal bar", async () => {
    open(fakeApi({
      getDaySummary: async () => ({ ...daySummaryA, totals: null, top_skus: [], by_department: [], vs_same_weekday_avg: null }),
    }));
    expect(await within(await screen.findByTestId("hero")).findByText("Sin datos")).toBeInTheDocument();
    expect(screen.queryByTestId("hero-delta")).toBeNull();
    expect(screen.queryByTestId("hero-bar")).toBeNull();
    expect(screen.getByTestId("metric-transactions")).toHaveTextContent("Sin datos");
    expect(screen.queryByTestId("top-product-1")).toBeNull();
  });
});

describe("DashboardPage activity chart", () => {
  const ids = (days: string[]) => days.map((d) => `activity-bar-${d}`);
  const actualDays = ["2026-02-23", "2026-02-24", "2026-02-25", "2026-02-26", "2026-02-27", "2026-02-28"];

  it("uses the simulated today as the day shown and asks for exactly that date", async () => {
    const api = fakeApi();
    open(api);
    await screen.findByTestId("hero");
    const calls = (api.getDaySummary as unknown as { mock: { calls: [string, string | undefined][] } }).mock.calls;
    expect(calls.some((c) => c[1] === "2026-03-01")).toBe(true);
    expect(calls.every((c) => c[1] !== undefined)).toBe(true);
  });

  it("draws 7 actual days ending at the simulated today, then the 3 days after it, highlighting today", async () => {
    open(fakeApi({ getForecast: async () => forecastFor() }));
    await screen.findByTestId("activity-bar-2026-03-01");
    for (const id of ids(actualDays)) expect(screen.getByTestId(id)).toHaveAttribute("data-kind", "actual");
    expect(screen.getByTestId("activity-bar-2026-03-01")).toHaveAttribute("data-kind", "today");
    for (const d of ["02", "03", "04"]) expect(screen.getByTestId(`activity-bar-2026-03-${d}`)).toHaveAttribute("data-kind", "forecast");
    expect(screen.queryByTestId("activity-bar-2026-03-05")).toBeNull();
    expect(within(screen.getByTestId("activity-col-2026-03-01")).getByText("hoy")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ventas por día" })).toBeInTheDocument();
    expect(screen.queryByText(/Actividad de hoy|por hora/)).toBeNull();
  });

  it("projects from the day after today with no gap", async () => {
    open(fakeApi({ getForecast: async () => forecastFor() }));
    const first = await screen.findByTestId("activity-bar-2026-03-02");
    const today = screen.getByTestId("activity-bar-2026-03-01");
    expect(today.closest("[data-testid^=activity-col]")!.nextElementSibling).toBe(first.closest("[data-testid^=activity-col]"));
  });

  it("never draws an actual in a projected bar, even if the payload carries one", async () => {
    const f = forecastFor();
    open(fakeApi({ getForecast: async () => ({ ...f, points: f.points.map((p) => ({ ...p, actual: 999 })) }) }));
    await screen.findByTestId("activity-bar-2026-03-02");
    expect(screen.getByTestId("activity-bar-2026-03-02")).toHaveAttribute("title", expect.stringContaining("$100.00"));
    expect(document.body.innerHTML).not.toContain("999");
  });

  it("shows the real value of the active bar in the tooltip, defaulting to today", async () => {
    open(fakeApi({ getForecast: async () => forecastFor() }));
    const tip = await screen.findByTestId("activity-tooltip");
    expect(tip).toHaveTextContent("$733.91");
    const { default: userEvent } = await import("@testing-library/user-event");
    await userEvent.hover(screen.getByTestId("activity-col-2026-03-03"));
    expect(tip).toHaveTextContent("$101.00");
    expect(tip).toHaveTextContent("proyección");
  });

  it("draws the tooltip pill dark, as in the design", async () => {
    open(fakeApi({ getForecast: async () => forecastFor() }));
    const tip = await screen.findByTestId("activity-tooltip");
    expect(tip.className).toContain("bg-primary");
    expect(tip.className).toContain("text-surface-bright");
    expect(tip.className).toContain("rounded-full");
    expect(tip.className).not.toMatch(/bg-surface|bg-outline/);
  });

  it("captions the forecast model as given by the backend", async () => {
    open(fakeApi({ getForecast: async () => forecastFor() }));
    expect(await screen.findByTestId("activity-model")).toHaveTextContent("glm_poisson");
  });

  it("keeps projected bars on the actuals' axis when they are within 1.5x", async () => {
    const f = forecastFor();
    open(fakeApi({ getForecast: async () => ({ ...f, points: f.points.map((p) => ({ ...p, forecast: 1000 })) }) }));
    await screen.findByTestId("activity-bar-2026-03-02");
    expect(screen.getByTestId("activity-bar-2026-03-02")).toHaveStyle({ height: "112px" });
    expect(screen.getByTestId("activity-bar-2026-03-01")).toHaveStyle({ height: "82px" });
    expect(screen.queryByTestId("activity-cap-2026-03-02")).toBeNull();
  });

  it("caps projected bars at the chart top with an arrow when they exceed 1.5x the actuals, without rescaling", async () => {
    const f = forecastFor();
    open(fakeApi({ getForecast: async () => ({ ...f, points: f.points.map((p, i) => ({ ...p, forecast: 2000 + i })) }) }));
    await screen.findByTestId("activity-bar-2026-03-02");
    expect(screen.getByTestId("activity-bar-2026-03-02")).toHaveStyle({ height: "112px" });
    expect(screen.getByTestId("activity-cap-2026-03-02")).toHaveTextContent("↑");
    expect(screen.getByTestId("activity-cap-2026-03-04")).toBeInTheDocument();
    expect(screen.getByTestId("activity-bar-2026-03-01")).toHaveStyle({ height: "112px" });
    expect(screen.getByTestId("activity-bar-2026-02-28")).toHaveStyle({ height: "112px" });
    expect(screen.getByTestId("activity-bar-2026-03-02")).toHaveAttribute("title", expect.stringContaining("$2,000.00"));
  });

  it("draws 7 actual days quietly, without a model caption, when the forecast route is missing", async () => {
    const api = fakeApi();
    open(api);
    await screen.findByTestId("activity-bar-2026-03-01");
    expect(screen.queryByTestId("activity-model")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    const dates = (api.getDaySummary as unknown as { mock: { calls: [string, string | undefined][] } }).mock.calls.map((c) => c[1]);
    expect(new Set(dates)).toEqual(new Set([...actualDays, "2026-03-01"]));
  });

  it("also stays quiet when the forecast route fails with a server error", async () => {
    open(fakeApi({ getForecast: vi.fn(async () => { throw new ApiError(500, "boom"); }) }));
    await screen.findByTestId("activity-bar-2026-03-01");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("keeps the today marker even when today has no sales", async () => {
    open(fakeApi({
      getDaySummary: vi.fn(async (_id: string, date?: string) => ({ ...daySummaryA, date: date ?? "", totals: date === "2026-03-01" ? null : daySummaryA.totals })),
    }));
    expect(await screen.findByTestId("activity-bar-2026-03-01")).toHaveAttribute("data-kind", "today");
  });

  it("marks a day without data", async () => {
    open(fakeApi({
      getDaySummary: vi.fn(async (_id: string, date?: string) => ({ ...daySummaryA, date: date ?? "", totals: date === "2026-02-27" ? null : daySummaryA.totals })),
    }));
    expect(await screen.findByTestId("activity-bar-2026-02-27")).toHaveAttribute("data-kind", "nodata");
  });

  it("asks for the 7 days before and after the simulated today", async () => {
    const api = fakeApi();
    open(api);
    await screen.findByTestId("hero");
    expect((api.getForecast as unknown as { mock: { calls: unknown[][] } }).mock.calls[0])
      .toEqual(["c1", { from: "2026-02-22", to: "2026-03-08", level: "store" }]);
  });
});

describe("DashboardPage favorites and footer", () => {
  it("lists the top 3 products with rank, initials, sales, bar and units", async () => {
    open();
    const first = await screen.findByTestId("top-product-1");
    expect(first).toHaveTextContent("50 Donut Holes");
    expect(first).toHaveTextContent("$105.00");
    expect(first).toHaveTextContent("5 uds.");
    expect(within(first).getByTestId("initials")).toHaveTextContent("DH");
    expect(within(first).getByTestId("rank")).toHaveTextContent("1");
    expect(screen.getByTestId("top-product-3")).toHaveTextContent("Vanilla Chai");
    expect(screen.getByTestId("top-product-3")).toHaveTextContent("VC");
    expect(screen.queryByTestId("top-product-4")).toBeNull();
  });

  it("links to the chat and shows the data timestamp", async () => {
    open();
    expect(await screen.findByRole("link", { name: /Preguntar al asistente/ })).toHaveAttribute("href", "/chat");
    expect(screen.getByText("Datos al 2026-03-11")).toBeInTheDocument();
  });
});
