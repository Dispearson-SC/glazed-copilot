import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CentinelaPanel from "./CentinelaPanel";
import { fakeApi, renderPage } from "./test/helpers";
import type { ComplianceRecord } from "./types";

const rec = (o: Partial<ComplianceRecord>): ComplianceRecord => ({
  decision_id: "d1", issue_id: "S030|stockout_risk|X", action_type: "place_order", status: "approved", applicable: true,
  execution: null, execution_status: "not_executed", horizon: null, simulated: null, observed: null, events: [],
  diagnosis: null, explanation: "", ...o,
});

const open = (rows: ComplianceRecord[]) =>
  renderPage(fakeApi({ getCompliance: async () => rows }), "/", "/", <CentinelaPanel caseId="c1" />);

describe("CentinelaPanel", () => {
  it("lists each decision with execution status, diagnosis and simulated vs observed (backtest)", async () => {
    open([
      rec({
        execution_status: "executed", diagnosis: "forecast_error", explanation: "fuera de rango",
        simulated: { net_usd_mid: 100, net_usd_low: 80, net_usd_high: 120, label: "simulated" },
        observed: { net_usd: 40, label: "backtest" },
      }),
      rec({ decision_id: "d2", diagnosis: "not_executed", explanation: "No se ejecutó" }),
    ]);
    expect(await screen.findByRole("heading", { name: "Centinela" })).toBeInTheDocument();
    expect(await screen.findByText("ejecutada")).toBeInTheDocument();
    expect(screen.getByText("Error de pronóstico")).toBeInTheDocument();
    expect(screen.getByText(/Simulado \$100\.00/)).toBeInTheDocument();
    expect(screen.getByText(/Observado \$40\.00 \(backtest\)/)).toBeInTheDocument();
    expect(screen.getByText("No ejecutada")).toBeInTheDocument();
  });

  it("shows an empty state", async () => {
    open([]);
    expect(await screen.findByText("Sin decisiones que verificar")).toBeInTheDocument();
  });
});
