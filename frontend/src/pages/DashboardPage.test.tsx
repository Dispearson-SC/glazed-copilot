import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api";
import { daySummaryA } from "../test/fixtures";
import { fakeApi, renderPage } from "../test/helpers";
import type { ForecastResponse } from "../types";
import DashboardPage from "./DashboardPage";

const open = (api = fakeApi()) => renderPage(api, "/", "/", <DashboardPage />);

const forecastFor = (over: Partial<ForecastResponse> = {}): ForecastResponse => {
  const days = Array.from({ length: 10 }, (_, i) => `2026-03-${String(4 + i).padStart(2, "0")}`);
  return {
    store_id: "S030", sku: null, level: "store", as_of: "2026-03-11", forecast_origin: "2026-03-11",
    model: "glm_poisson", model_version: "1", unit: "USD", horizon_days: 7,
    points: days.map((date, i) => ({
      date, forecast: 100 + i, p10: 80, p90: 120, baseline: 90, actual: date <= "2026-03-10" ? 200 + i : 999, censored: false,
    })),
    metrics_to_date: { wape: 0.298, bias: 0, coverage_p10_p90: 0.88, wape_baseline: 0.357, n_days: 28 },
    ...over,
  };
};

describe("DashboardPage header", () => {
  it("shows the title, the long Spanish date of the summary and the simulated clock", async () => {
    open();
    expect(await screen.findByRole("heading", { name: "Resumen de hoy" })).toBeInTheDocument();
    expect(screen.getByText("martes, 10 de marzo de 2026")).toBeInTheDocument();
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
    expect(screen.getByTestId("hero-delta")).toHaveTextContent("+18.8% vs promedio mismo día");
    expect(hero).toHaveTextContent("Promedio mismo día (8 sem): $617.92");
    expect(screen.getByTestId("hero-progress")).toHaveTextContent("119% del promedio");
    expect(screen.getByTestId("hero-bar")).toHaveStyle({ width: "100%" });
  });

  it("caps the bar below the average and uses the weeks reported by the backend", async () => {
    open(fakeApi({
      getDaySummary: async () => ({ ...daySummaryA, totals: { ...daySummaryA.totals, net_sales: 308.96 }, vs_same_weekday_avg: { baseline_net_sales: 617.92, weeks_used: 7, delta_pct: -50 } }),
    }));
    expect(await screen.findByTestId("hero-progress")).toHaveTextContent("50% del promedio");
    expect(screen.getByTestId("hero")).toHaveTextContent("(7 sem)");
    expect(screen.getByTestId("hero-bar")).toHaveStyle({ width: "50%" });
    expect(screen.getByTestId("hero-delta")).toHaveTextContent("-50.0%");
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
  it("draws the 7 days ending at the summary date plus 3 projected days, highlighting the day shown", async () => {
    const api = fakeApi({ getForecast: async () => forecastFor() });
    open(api);
    await screen.findByTestId("activity-bar-2026-03-10");
    for (const d of ["04", "05", "06", "07", "08", "09", "10"]) expect(screen.getByTestId(`activity-bar-2026-03-${d}`)).toHaveAttribute("data-kind", d === "10" ? "today" : "actual");
    for (const d of ["11", "12", "13"]) expect(screen.getByTestId(`activity-bar-2026-03-${d}`)).toHaveAttribute("data-kind", "forecast");
    expect(screen.queryByTestId("activity-bar-2026-03-14")).toBeNull();
    expect(within(screen.getByTestId("activity-col-2026-03-10")).getByText("hoy")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ventas por día" })).toBeInTheDocument();
    expect(screen.queryByText(/Actividad de hoy|por hora/)).toBeNull();
  });

  it("never draws an actual dated after the summary day, even if the payload carries one", async () => {
    open(fakeApi({ getForecast: async () => forecastFor() }));
    await screen.findByTestId("activity-bar-2026-03-11");
    expect(screen.getByTestId("activity-bar-2026-03-11")).toHaveAttribute("title", expect.stringContaining("$107.00"));
    expect(screen.queryByText(/999/)).toBeNull();
    expect(document.body.innerHTML).not.toContain("999");
  });

  it("shows the real value of the active bar in the tooltip, defaulting to the day shown", async () => {
    open(fakeApi({ getForecast: async () => forecastFor() }));
    const tip = await screen.findByTestId("activity-tooltip");
    expect(tip).toHaveTextContent("$733.91");
    const { default: userEvent } = await import("@testing-library/user-event");
    await userEvent.hover(screen.getByTestId("activity-col-2026-03-12"));
    expect(tip).toHaveTextContent("$108.00");
    expect(tip).toHaveTextContent("proyección");
  });

  it("captions the forecast model as given by the backend", async () => {
    open(fakeApi({ getForecast: async () => forecastFor() }));
    expect(await screen.findByTestId("activity-model")).toHaveTextContent("glm_poisson");
  });

  it("draws 7 actual days quietly, without a model caption, when the forecast route is missing", async () => {
    const api = fakeApi();
    open(api);
    await screen.findByTestId("activity-bar-2026-03-10");
    expect(screen.queryByTestId("activity-model")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    const dates = (api.getDaySummary as unknown as { mock: { calls: [string, string | undefined][] } }).mock.calls.map((c) => c[1]).filter(Boolean);
    expect(new Set(dates)).toEqual(new Set(["2026-03-04", "2026-03-05", "2026-03-06", "2026-03-07", "2026-03-08", "2026-03-09"]));
  });

  it("also stays quiet when the forecast route fails with a server error", async () => {
    open(fakeApi({ getForecast: vi.fn(async () => { throw new ApiError(500, "boom"); }) }));
    await screen.findByTestId("activity-bar-2026-03-10");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("takes actuals from day summaries even when the forecast carries none for the past", async () => {
    const f = forecastFor();
    open(fakeApi({ getForecast: async () => ({ ...f, points: f.points.map((p) => ({ ...p, actual: null })) }) }));
    await screen.findByTestId("activity-bar-2026-03-09");
    expect(screen.getByTestId("activity-bar-2026-03-09")).toHaveAttribute("data-kind", "actual");
    expect(screen.getByTestId("activity-bar-2026-03-09")).toHaveAttribute("title", expect.stringContaining("$733.91"));
  });

  it("keeps the day-shown marker even when that day has no sales", async () => {
    open(fakeApi({
      getDaySummary: vi.fn(async (_id: string, date?: string) => ({ ...daySummaryA, date: date ?? "2026-03-10", totals: date === undefined ? null : daySummaryA.totals })),
    }));
    expect(await screen.findByTestId("activity-bar-2026-03-10")).toHaveAttribute("data-kind", "today");
  });

  it("marks a day without data", async () => {
    open(fakeApi({
      getDaySummary: vi.fn(async (_id: string, date?: string) => ({
        ...daySummaryA, date: date ?? "2026-03-10", totals: date === "2026-03-08" ? null : daySummaryA.totals,
      })),
    }));
    expect(await screen.findByTestId("activity-bar-2026-03-08")).toHaveAttribute("data-kind", "nodata");
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
