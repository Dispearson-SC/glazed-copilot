import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { daySummaryA } from "../test/fixtures";
import { fakeApi, renderPage } from "../test/helpers";
import DashboardPage from "./DashboardPage";

const open = (api = fakeApi()) => renderPage(api, "/", "/", <DashboardPage />);

describe("DashboardPage states", () => {
  it("shows an empty state without a case", async () => {
    open(fakeApi({ listCases: async () => [] }));
    expect(await screen.findByText("Sin caso activo para esta sucursal")).toBeInTheDocument();
  });

  it("shows an error, not 'Sin datos', when the day-summary request fails", async () => {
    open(fakeApi({ getDaySummary: async () => { throw new Error("fecha posterior a as_of"); } }));
    expect(await screen.findByText(/fecha posterior a as_of/)).toBeInTheDocument();
    expect(screen.queryByTestId("hero")).toBeNull();
  });
});

describe("DashboardPage metrics", () => {
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

  it("shows 'Sin datos' (not zero) when totals is null, with an empty goal bar", async () => {
    open(fakeApi({
      getDaySummary: async () => ({ ...daySummaryA, totals: null, top_skus: [], by_department: [], vs_same_weekday_avg: null }),
    }));
    const hero = await screen.findByTestId("hero");
    expect(within(hero).getAllByText("Sin datos").length).toBeGreaterThan(0);
    expect(screen.getByTestId("hero-bar")).toHaveStyle({ width: "0%" });
    expect(screen.getByTestId("hero-delta")).toHaveTextContent("Sin datos vs ayer");
    expect(screen.getByTestId("metric-transactions")).toHaveTextContent("Sin datos");
    expect(screen.queryByTestId("top-product-1")).toBeNull();
  });
});

describe("DashboardPage favorites", () => {
  it("lists the top 3 products with rank, initials, sales, bar and units", async () => {
    open();
    const first = await screen.findByTestId("top-product-1");
    expect(first).toHaveTextContent("50 Donut Holes");
    expect(first).toHaveTextContent("$105.00");
    expect(first).toHaveTextContent("5 uds.");
    expect(first).toHaveTextContent("Precio promedio • $21.00");
    expect(within(first).getByTestId("initials")).toHaveTextContent("DH");
    expect(within(first).getByTestId("rank")).toHaveTextContent("1");
    expect(screen.getByTestId("top-product-3")).toHaveTextContent("Vanilla Chai");
    expect(screen.getByTestId("top-product-3")).toHaveTextContent("VC");
    expect(screen.queryByTestId("top-product-4")).toBeNull();
  });
});
