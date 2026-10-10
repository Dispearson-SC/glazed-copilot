import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { forecastA } from "../test/fixtures";
import ForecastChart from "./ForecastChart";

describe("ForecastChart", () => {
  const show = (f = forecastA) => render(<ForecastChart forecast={f} />);

  it("marks today (as_of) with a hoy marker", () => {
    show();
    expect(within(screen.getByTestId("fc-col-2026-03-01")).getByText("hoy")).toBeInTheDocument();
    expect(within(screen.getByTestId("fc-col-2026-03-02")).queryByText("hoy")).toBeNull();
  });

  it("draws actuals only up to as_of, even if the payload carries a later one", () => {
    show();
    expect(screen.getByTestId("fc-actual-2026-02-27")).toBeInTheDocument();
    expect(screen.getByTestId("fc-actual-2026-03-01")).toBeInTheDocument();
    expect(screen.queryByTestId("fc-actual-2026-03-02")).toBeNull();
    expect(screen.queryByTestId("fc-actual-2026-03-03")).toBeNull();
    expect(screen.queryByText(/999/)).toBeNull();
  });

  it("draws the forecast with its p10-p90 band for future days, labelled as projection", () => {
    show();
    expect(screen.getByTestId("fc-forecast-2026-03-02")).toBeInTheDocument();
    expect(screen.getByTestId("fc-band-2026-03-02")).toHaveAttribute("title", expect.stringContaining("$95.00 – $150.00"));
    expect(screen.getAllByText(/Proyección/).length).toBeGreaterThan(0);
  });

  it("shows the model exactly as given and the metrics against the baseline", () => {
    show();
    expect(screen.getByTestId("forecast-model")).toHaveTextContent("baseline-weekday-8w");
    const m = screen.getByTestId("forecast-metrics");
    expect(m).toHaveTextContent("12.3%");
    expect(m).toHaveTextContent("línea base 20.0%");
    expect(m).toHaveTextContent("28 días");
    expect(m).toHaveTextContent("80%");
  });

  it("flags censored days (stockout) so lower actuals are not read as low demand", () => {
    show();
    expect(screen.getByTestId("fc-censored-2026-02-28")).toHaveAttribute("title", expect.stringContaining("5"));
  });

  it("labels the band as a sum over products at store level", () => {
    show();
    expect(screen.getByTestId("forecast-band-note")).toHaveTextContent("rango (suma por producto)");
  });

  it("does not count censored days as misses and says how many there are", () => {
    show();
    expect(screen.getByTestId("forecast-metrics")).toHaveTextContent("3 días con quiebre no cuentan como error");
    expect(screen.getByTestId("fc-actual-2026-02-28")).toHaveAttribute("data-censored", "true");
    expect(screen.getByTestId("fc-actual-2026-02-27")).toHaveAttribute("data-censored", "false");
  });
});
