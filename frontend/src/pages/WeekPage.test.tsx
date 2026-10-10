import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { deliveriesA, promosA, staffingA } from "../test/fixtures";
import { fakeApi, renderPage } from "../test/helpers";
import WeekPage from "./WeekPage";

const ok = () => fakeApi({ getDeliveries: async () => deliveriesA, getPromos: async () => promosA, getStaffing: async () => staffingA });
const open = (api = ok()) => renderPage(api, "/stores/S030/week", "/stores/:storeId/week", <WeekPage />);

describe("WeekPage", () => {
  it("lists deliveries by day with supplier, lines, value and status", async () => {
    open();
    const d = await screen.findByTestId("delivery-2026-03-02");
    expect(d).toHaveTextContent("Panificadora Norte");
    expect(d).toHaveTextContent("PO-7");
    expect(d).toHaveTextContent("Dona glaseada");
    expect(d).toHaveTextContent("48");
    expect(d).toHaveTextContent("$120.00");
    expect(d).toHaveTextContent("tarde");
    expect(screen.getByTestId("delivery-2026-03-03")).toHaveTextContent("Sin entregas");
  });

  it("shows promos with their audit verdict and only evaluates finished ones", async () => {
    open();
    const past = await screen.findByTestId("promo-pr1");
    expect(past).toHaveTextContent("2x1 donas");
    expect(past).toHaveTextContent("50%");
    expect(past).toHaveTextContent("engañosa");
    expect(past).toHaveTextContent("+12.5%");
    const next = screen.getByTestId("promo-pr2");
    expect(next).toHaveTextContent("Café combo");
    expect(next).not.toHaveTextContent("99");
  });

  it("states staffing is daily only, with recommended hours and gaps", async () => {
    open();
    await screen.findByTestId("staffing-2026-03-02");
    const s = screen.getByTestId("staffing");
    expect(s).toHaveTextContent(/solo por día/i);
    expect(s).toHaveTextContent("Estimación diaria con el benchmark del formato.");
    expect(within(screen.getByTestId("staffing-2026-03-02")).getByText("30.0 h")).toBeInTheDocument();
    expect(screen.getByTestId("staffing-2026-03-02")).toHaveTextContent("+6.0 h");
    expect(screen.getByTestId("staffing-2026-03-03")).toHaveTextContent("Sin datos");
  });

  it("shows Disponible pronto in each section when the routes are missing", async () => {
    open(fakeApi());
    await waitFor(() => expect(screen.getAllByTestId("soon")).toHaveLength(3));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
