import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { alertA, fakeApi, renderPage } from "../test/helpers";
import { daySummaryA } from "../test/fixtures";
import HomePage from "./HomePage";

const open = (api = fakeApi()) => renderPage(api, "/", "/", <HomePage />);

describe("HomePage", () => {
  it("offers stores by display name", async () => {
    open();
    expect(await screen.findByRole("option", { name: "Aeropuerto Norte · Glazed Centro" })).toBeInTheDocument();
  });

  it("shows both losses side by side: waste and lost sales as a range", async () => {
    open();
    const waste = await screen.findByTestId("loss-waste");
    const lost = screen.getByTestId("loss-lost-sales");
    expect(within(waste).getByText("$310.50")).toBeInTheDocument();
    expect(within(lost).getByText("$180.25")).toBeInTheDocument();
    expect(within(lost).getByText("$100.00 – $260.00")).toBeInTheDocument();
    expect(screen.getByText(/2026-02-15/)).toBeInTheDocument();
  });

  it("builds a semaphore from open alerts by severity", async () => {
    const api = fakeApi({
      listAlerts: async () => [
        { ...alertA, alert_id: "a1", severity_usd: 600 },
        { ...alertA, alert_id: "a2", severity_usd: 200 },
        { ...alertA, alert_id: "a3", severity_usd: 20 },
        { ...alertA, alert_id: "a4", severity_usd: 900, state: "resuelta" },
      ],
    });
    open(api);
    await waitFor(() => expect(screen.getByTestId("sem-red")).toHaveTextContent("1"));
    expect(screen.getByTestId("sem-yellow")).toHaveTextContent("1");
    expect(screen.getByTestId("sem-green")).toHaveTextContent("1");
  });

  it("links to purchases and alerts", async () => {
    open();
    expect(await screen.findByRole("link", { name: "Ver compras" })).toHaveAttribute("href", "/stores/S030/purchases");
    expect(screen.getByRole("link", { name: "Ver alertas" })).toHaveAttribute("href", "/alerts");
    expect(screen.getByRole("link", { name: "Ver inventario" })).toHaveAttribute("href", "/stores/S030/inventory");
    expect(screen.getByRole("link", { name: "Ver semana" })).toHaveAttribute("href", "/stores/S030/week");
  });

  it("shows an error state when kpis fail", async () => {
    open(fakeApi({ getKpis: async () => { throw new Error("sin kpis"); } }));
    expect(await screen.findByRole("alert")).toHaveTextContent("sin kpis");
  });

  it("shows an empty state without a case", async () => {
    open(fakeApi({ listCases: async () => [] }));
    expect(await screen.findByText("Sin caso activo para esta sucursal")).toBeInTheDocument();
  });
});

describe("HomePage dashboard", () => {
  const spy = (api: ReturnType<typeof fakeApi>) =>
    (api.getDaySummary as unknown as { mock: { calls: [string, string | undefined][] } }).mock.calls;

  it("shows the day net sales with the delta against the same-weekday average", async () => {
    open();
    expect(await within(await screen.findByTestId("hero")).findByText("$733.91")).toBeInTheDocument();
    expect(screen.getByTestId("hero-delta")).toHaveTextContent("+18.8%");
    expect(screen.getByTestId("hero")).toHaveTextContent("promedio de 8 semanas");
    expect(screen.getByTestId("hero")).toHaveTextContent("$617.92");
    expect(screen.getByTestId("hero")).toHaveTextContent("2026-03-10");
  });

  it("maps transactions, average ticket and units, without staff hours", async () => {
    open();
    expect(await screen.findByTestId("metric-transactions")).toHaveTextContent("74");
    expect(screen.getByTestId("metric-avg-ticket")).toHaveTextContent("$9.92");
    expect(screen.getByTestId("metric-units")).toHaveTextContent("138");
    expect(screen.queryByText(/36\.2/)).toBeNull();
  });

  it("guards the average ticket when there are no transactions", async () => {
    const api = fakeApi({
      getDaySummary: async () => ({ ...daySummaryA, totals: { ...daySummaryA.totals, transactions: 0 } }),
    });
    open(api);
    expect(await screen.findByTestId("metric-avg-ticket")).toHaveTextContent("—");
  });

  it("shows 'Sin datos' (not zero) when totals is null and no delta", async () => {
    const api = fakeApi({
      getDaySummary: async () => ({ ...daySummaryA, totals: null, top_skus: [], by_department: [], vs_same_weekday_avg: null }),
    });
    open(api);
    expect(await within(await screen.findByTestId("hero")).findByText("Sin datos")).toBeInTheDocument();
    expect(screen.queryByTestId("hero-delta")).toBeNull();
    expect(screen.getByTestId("metric-transactions")).toHaveTextContent("Sin datos");
    expect(screen.queryByTestId("top-product-1")).toBeNull();
  });

  it("shows an error, not 'Sin datos', when the day-summary request fails (HTTP 400)", async () => {
    const api = fakeApi({ getDaySummary: async () => { throw new Error("fecha posterior a as_of"); } });
    open(api);
    expect(await screen.findByText(/fecha posterior a as_of/)).toBeInTheDocument();
    expect(screen.queryByText("Sin datos")).toBeNull();
  });

  it("draws a 7-day trend ending at the summary date and marks missing days", async () => {
    const api = fakeApi({
      getDaySummary: vi.fn(async (_id: string, date?: string) => ({
        ...daySummaryA,
        date: date ?? "2026-03-10",
        totals: date === "2026-03-08" ? null : { ...daySummaryA.totals, net_sales: 500 },
      })),
    });
    open(api);
    await screen.findByTestId("trend-bar-2026-03-10");
    for (const d of ["04", "05", "06", "07", "09", "10"]) expect(screen.getByTestId(`trend-bar-2026-03-${d}`)).toBeInTheDocument();
    expect(screen.queryByTestId("trend-bar-2026-03-08")).toBeNull();
    expect(screen.getByTestId("trend-nodata-2026-03-08")).toHaveTextContent("sin datos");
    const dates = spy(api).map((c) => c[1]).filter(Boolean);
    expect(new Set(dates)).toEqual(new Set(["2026-03-04", "2026-03-05", "2026-03-06", "2026-03-07", "2026-03-08", "2026-03-09"]));
  });

  it("lists the top 3 products by name, sales and units", async () => {
    open();
    const first = await screen.findByTestId("top-product-1");
    expect(first).toHaveTextContent("50 Donut Holes");
    expect(first).toHaveTextContent("$105.00");
    expect(first).toHaveTextContent("5 uds");
    expect(screen.getByTestId("top-product-3")).toHaveTextContent("Vanilla Chai");
    expect(screen.queryByTestId("top-product-4")).toBeNull();
  });

  it("shows context chips and the observed weather", async () => {
    open();
    expect(await screen.findByText("Día de prueba")).toBeInTheDocument();
    expect(screen.getByTestId("weather")).toHaveTextContent("Clima observado");
    expect(screen.getByTestId("weather")).toHaveTextContent("24.7°");
  });

  it("shows the briefing headline, lost sales as a range and the order plan counts", async () => {
    open();
    const b = await screen.findByTestId("briefing");
    expect(await within(b).findByText("Merma 7 días $1,361")).toBeInTheDocument();
    expect(within(b).getByText("Venta perdida estimada $40–$565")).toBeInTheDocument();
    expect(within(b).getByTestId("due-today")).toHaveTextContent("1");
    expect(within(b).getByTestId("due-tomorrow")).toHaveTextContent("2");
    expect(within(b).getByTestId("focus")).toHaveTextContent("2");
  });

  it("does not break the dashboard when the briefing fails", async () => {
    open(fakeApi({ getBriefing: async () => { throw new Error("sin briefing"); } }));
    expect(await screen.findByTestId("hero")).toBeInTheDocument();
    expect(await screen.findByText(/sin briefing/)).toBeInTheDocument();
  });
});

describe("HomePage Lo que viene", () => {
  it("renders the upcoming card from briefing and order plan", async () => {
    const { briefingLive, planLive } = await import("../test/fixtures");
    open(fakeApi({ getBriefing: async () => briefingLive, getOrderPlan: async () => planLive }));
    expect(await screen.findByTestId("upcoming")).toHaveTextContent("Lo que viene");
    expect(await screen.findByTestId("upcoming-stockouts")).toHaveTextContent("Cold Foam");
  });

  it("keeps the rest of Home when the order plan fails", async () => {
    open(fakeApi({ getOrderPlan: async () => { throw new Error("plan caído"); } }));
    expect(await screen.findByTestId("hero")).toBeInTheDocument();
    expect(await screen.findByText(/plan caído/)).toBeInTheDocument();
  });
});

describe("HomePage forecast overlay", () => {
  it("falls back to the plain 7-day trend, quietly, when the forecast route is missing", async () => {
    open();
    await screen.findByTestId("trend-bar-2026-03-10");
    expect(screen.queryByTestId("forecast-chart")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows the forecast chart when the route answers", async () => {
    const { forecastA } = await import("../test/fixtures");
    open(fakeApi({ getForecast: async () => forecastA }));
    expect(await screen.findByTestId("forecast-chart")).toBeInTheDocument();
    expect(screen.getByTestId("forecast-model")).toHaveTextContent("baseline-weekday-8w");
  });

  it("asks for the 7 days before and after the simulated today", async () => {
    const api = fakeApi();
    open(api);
    await screen.findByTestId("hero");
    const call = (api.getForecast as unknown as { mock: { calls: unknown[][] } }).mock.calls[0];
    expect(call).toEqual(["c1", { from: "2026-02-22", to: "2026-03-08", level: "store" }]);
  });

  it("shows the accuracy table under the chart when the route answers, and stays quiet otherwise", async () => {
    const { forecastA, accuracyA } = await import("../test/fixtures");
    const { unmount } = open(fakeApi({ getForecast: async () => forecastA, getForecastAccuracy: async () => accuracyA }));
    expect(await screen.findByTestId("accuracy")).toBeInTheDocument();
    unmount();
    open(fakeApi({ getForecast: async () => forecastA }));
    await screen.findByTestId("forecast-chart");
    expect(screen.queryByTestId("accuracy")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
