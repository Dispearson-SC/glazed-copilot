import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { accuracyA } from "../test/fixtures";
import ForecastAccuracy from "./ForecastAccuracy";

describe("ForecastAccuracy", () => {
  it("lists one row per shelf-life group with readable labels, in a fixed order", () => {
    render(<ForecastAccuracy accuracy={accuracyA} />);
    const rows = within(screen.getByTestId("accuracy")).getAllByRole("row").slice(1);
    expect(rows.map((r) => r.querySelector("th")?.textContent)).toEqual(["1 día", "2–3 días", "4–14 días", "No perecedero", "Total"]);
    expect(rows[0]).toHaveTextContent("42.4%");
    expect(rows[0]).toHaveTextContent("176");
  });

  it("reports censored days apart, as not counted in the error", () => {
    render(<ForecastAccuracy accuracy={accuracyA} />);
    expect(screen.getByTestId("accuracy-row-1")).toHaveTextContent("18 con quiebre");
    expect(screen.getByTestId("accuracy")).toHaveTextContent(/quiebre.*no cuentan/i);
  });

  it("shows model and window", () => {
    render(<ForecastAccuracy accuracy={accuracyA} />);
    expect(screen.getByTestId("accuracy")).toHaveTextContent("baseline-weekday-8w");
    expect(screen.getByTestId("accuracy")).toHaveTextContent("2026-02-01");
  });
});
