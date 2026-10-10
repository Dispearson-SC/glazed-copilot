import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { briefingLive, planLive } from "../test/fixtures";
import UpcomingCard from "./UpcomingCard";

const show = (over: Partial<Parameters<typeof UpcomingCard>[0]> = {}) =>
  render(<UpcomingCard briefing={briefingLive} plan={planLive} error={null} {...over} />);

describe("UpcomingCard (Lo que viene)", () => {
  it("lists orders due today and tomorrow with the deadline as a date and no hour", () => {
    show();
    const today = screen.getByTestId("upcoming-today");
    expect(within(today).getByText("Cold Foam")).toBeInTheDocument();
    expect(within(today).getByText("Sand")).toBeInTheDocument();
    expect(within(today).getAllByText(/hora no disponible/i)).toHaveLength(2);
    expect(within(today).getAllByText(/2026-07-19/).length).toBeGreaterThan(0);
    const tomorrow = screen.getByTestId("upcoming-tomorrow");
    expect(within(tomorrow).getByText("Coffee Beans")).toBeInTheDocument();
    expect(within(tomorrow).getByText(/2026-07-20/)).toBeInTheDocument();
  });

  it("shows qty, cases and the estimated cost of each order", () => {
    show();
    const row = screen.getByTestId("upcoming-today-SKU-1");
    expect(row).toHaveTextContent("10 pzas");
    expect(row).toHaveTextContent("1 caja");
    expect(row).toHaveTextContent("$14.60");
  });

  it("orders next stockouts by projected date and skips lines without one", () => {
    show();
    const list = screen.getByTestId("upcoming-stockouts");
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Cold Foam");
    expect(rows[0]).toHaveTextContent("2026-07-21");
    expect(rows[0]).toHaveTextContent("99.7%");
    expect(rows[0]).toHaveTextContent("40.0%");
    expect(rows[1]).toHaveTextContent("Sand");
    expect(within(list).queryByText("Never runs out")).toBeNull();
  });

  it("shows the expected waste as a range (sum of the order lines)", () => {
    show();
    const waste = screen.getByTestId("upcoming-waste");
    expect(waste).toHaveTextContent("$0.39 – $3.38");
    expect(waste).toHaveTextContent("$1.46");
  });

  it("surfaces the worst supplier headline and suppliers under their minimum order", () => {
    show();
    expect(screen.getByTestId("upcoming-worst-supplier")).toHaveTextContent("Pioneer Merch & Packaging (85.7%)");
    const mins = screen.getByTestId("upcoming-min-order");
    expect(mins).toHaveTextContent("Summit Frozen Foods");
    expect(mins).toHaveTextContent("$106.10");
    expect(mins).toHaveTextContent("$300.00");
  });

  it("renders quiet empty states instead of fabricating data", () => {
    show({ briefing: { snapshot: { order_plan: { due_today: [], due_tomorrow: [] } } }, plan: { ...planLive, lines: [], suppliers: [] } });
    expect(screen.getByTestId("upcoming-today")).toHaveTextContent("Sin pedidos para hoy");
    expect(screen.getByTestId("upcoming-tomorrow")).toHaveTextContent("Sin pedidos para mañana");
    expect(screen.getByText("Sin quiebres proyectados")).toBeInTheDocument();
    expect(screen.queryByTestId("upcoming-waste")).toBeNull();
  });

  it("accepts the legacy numeric waste shape", () => {
    show({ plan: { ...planLive, lines: [{ ...planLive.lines[0], expected_waste_usd: 20 }] } });
    expect(screen.getByTestId("upcoming-waste")).toHaveTextContent("$20.00");
  });

  it("shows the error without hiding the briefing part", () => {
    show({ plan: null, error: new Error("sin plan") });
    expect(screen.getByRole("alert")).toHaveTextContent("sin plan");
    expect(screen.getByTestId("upcoming-today")).toBeInTheDocument();
  });
});
