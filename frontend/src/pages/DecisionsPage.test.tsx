import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api";
import { decisionsA } from "../test/fixtures";
import { fakeApi, renderPage } from "../test/helpers";
import { useSession } from "../SessionContext";
import DecisionsPage from "./DecisionsPage";

const open = (api = fakeApi({ getDecisions: async () => decisionsA })) =>
  renderPage(api, "/stores/S030/decisions", "/stores/:storeId/decisions", <DecisionsPage />);

describe("DecisionsPage", () => {
  it("groups rows by decision, in order, with a step per row", async () => {
    open();
    const g = await screen.findByTestId("decision-p1");
    const steps = within(g).getAllByRole("listitem").map((li) => li.textContent);
    expect(steps[0]).toContain("Propuesta");
    expect(steps[1]).toContain("Aprobada");
    expect(steps[1]).toContain("Va la promo");
    expect(steps[2]).toContain("Ejecución");
    expect(steps[3]).toContain("Resultado");
    expect(g).toHaveTextContent("DONUT-GLZ");
    expect(screen.getByTestId("decision-p3")).toHaveTextContent("Rechazada");
    expect(screen.getByTestId("decision-p3")).toHaveTextContent("Sin presupuesto");
    expect(screen.getByTestId("decision-p2")).toHaveTextContent("Pedido omitido");
  });

  it("compares expected (range) against observed and keeps the backtest label", async () => {
    open();
    const o = await screen.findByTestId("outcome-p1");
    expect(o).toHaveTextContent("Esperado $80.00");
    expect(o).toHaveTextContent("$20.00 – $160.00");
    expect(o).toHaveTextContent("Observado $55.00");
    expect(o).toHaveTextContent("backtest");
    expect(o).toHaveTextContent("dentro del rango");
  });

  it("never shows an outcome measured after the simulated today", async () => {
    open(); // caseA.sim_today = 2026-03-01; p4 outcome ends 2026-03-04
    await screen.findByTestId("decision-p1");
    expect(screen.queryByTestId("decision-p4")).toBeNull();
    expect(screen.queryByText(/999/)).toBeNull();
  });

  it("says Disponible pronto, not an error, when the route is missing", async () => {
    open(fakeApi({ getDecisions: async () => { throw new ApiError(404, "Not Found"); } }));
    expect(await screen.findByTestId("soon")).toHaveTextContent("Disponible pronto");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows an empty state", async () => {
    open(fakeApi({ getDecisions: async () => [] }));
    expect(await screen.findByText("Aún no hay decisiones en este caso")).toBeInTheDocument();
  });

  it("refetches after the simulated clock advances", async () => {
    const getDecisions = vi.fn(async () => decisionsA);
    function Bump() {
      const s = useSession();
      return <button onClick={s.bump}>avanzar</button>;
    }
    renderPage(fakeApi({ getDecisions }), "/stores/S030/decisions", "/stores/:storeId/decisions", <><Bump /><DecisionsPage /></>);
    await screen.findByTestId("decision-p1");
    const n = getDecisions.mock.calls.length;
    await userEvent.click(screen.getByText("avanzar"));
    await waitFor(() => expect(getDecisions.mock.calls.length).toBeGreaterThan(n));
  });
});
