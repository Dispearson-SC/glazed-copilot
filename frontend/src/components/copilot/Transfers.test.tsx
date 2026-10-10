import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api";
import { ApiProvider } from "../../ApiContext";
import { buildPendingItems, buildWarnings } from "../../data/copilot";
import CopilotPage from "../../pages/CopilotPage";
import { analysisApproval, pendingA } from "../../test/copilotFixtures";
import { caseA, fakeApi, renderPage } from "../../test/helpers";
import type { TransferOptionsResponse } from "../../types";
import TransferOptions from "./TransferOptions";

const option = {
  option_id: "a899c3d5698f", sku: "SKU-100263", product_name: "Md Choc Stout", from_store: "S001", to_store: "S003", to_store_name: "Terminal C", qty: 8,
  transfer_cost_usd: 15.8, net_usd: { low: 17.84, mid: 20.92, high: 20.92 }, confidence: { score: 0.3, calibrated: false }, expires_on: "2026-07-20",
  rationale_es: "Trasladar 8 cuesta $15.80 y evita merma.",
};
const withOptions: TransferOptionsResponse = { as_of: "2026-07-19", store_id: "S001", options: [option] };

const show = (getTransferOptions: unknown) =>
  render(
    <ApiProvider api={fakeApi({ getTransferOptions })}>
      <TransferOptions caseId="c1" />
    </ApiProvider>,
  );

describe("TransferOptions", () => {
  it("shows a skeleton while loading, then each option with store, qty, cost, net range, confidence, expiry and rationale", async () => {
    let release!: (v: TransferOptionsResponse) => void;
    show(() => new Promise((r) => (release = r)));
    expect(screen.getByRole("status", { name: /Cargando traslados/ })).toHaveAttribute("aria-busy", "true");
    release(withOptions);
    const card = await screen.findByTestId("transfer-option");
    expect(within(card).getByText("Terminal C")).toBeInTheDocument();
    expect(card).toHaveTextContent("8 unidades");
    expect(card).toHaveTextContent("Costo $15.80");
    expect(card).toHaveTextContent("Neto +$17.84 a +$20.92");
    expect(card).toHaveTextContent("Confianza 30%");
    expect(card).toHaveTextContent("Vence el 2026-07-20");
    expect(card).toHaveTextContent("Trasladar 8 cuesta $15.80 y evita merma.");
    expect(screen.queryByRole("status", { name: /Cargando traslados/ })).toBeNull();
  });

  it("empty options say why in Spanish, never the code", async () => {
    show(async () => ({ as_of: "x", store_id: "S001", options: [], reason: "no_receiver_deficit" }));
    expect(await screen.findByText("Ninguna tienda necesita este producto")).toBeInTheDocument();
    expect(screen.queryByText(/no_receiver_deficit/)).toBeNull();
  });

  it("prefers the backend's reason_es", async () => {
    show(async () => ({ as_of: "x", store_id: "S001", options: [], reason: "otra", reason_es: "Sin excedente en esta sucursal" }));
    expect(await screen.findByText("Sin excedente en esta sucursal")).toBeInTheDocument();
  });

  it("404 says Disponible pronto", async () => {
    show(async () => { throw new ApiError(404, "Not Found"); });
    expect(await screen.findByText("Disponible pronto")).toBeInTheDocument();
  });

  it("other errors are shown", async () => {
    show(async () => { throw new ApiError(500, "boom"); });
    expect(await screen.findByText(/No se pudieron cargar los traslados: boom/)).toBeInTheDocument();
  });
});

describe("transfer_opportunity decisions", () => {
  const transfer = {
    ...pendingA.approvals[0],
    issue_id: "S030|transfer_opportunity|SKU-100263", kind: "transfer_opportunity", kinds: ["transfer_opportunity"], tier: "N3",
    recommendation: { option_id: "a899c3d5698f", label: "Trasladar 8 unidades a Terminal C", action_type: "transfer_stock", params: {} },
  };
  const pending = { ...pendingA, approvals: [transfer], technical: [] };

  it("builds a card with the transfer icon, the Spanish kind label and the option to decide", () => {
    const [card] = buildPendingItems(pending, "2026-07-19");
    expect(card).toMatchObject({ optionId: "a899c3d5698f", icon: "swap_horiz", kinds: ["Oportunidad de traslado"], kind: "approval", isTransfer: true });
  });

  it("opens Analizar with the transfer options and decides through POST /decisions", async () => {
    const recordDecision = vi.fn(async () => ({ decision_id: "d", proposal_id: "p", status: "approved" }));
    const getTransferOptions = vi.fn(async () => withOptions);
    const api = fakeApi({
      listCases: async () => [{ ...caseA, sim_today: "2026-07-19" }], getPending: async () => pending, recordDecision, getTransferOptions,
      getAnalysis: async () => ({ ...analysisApproval, issue_id: transfer.issue_id }),
    });
    renderPage(api, "/copiloto", "/copiloto", <CopilotPage />);
    await userEvent.click(await screen.findByRole("button", { name: /^Decisiones/ }));
    expect(await screen.findByText("Oportunidad de traslado")).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "Analizar con el copiloto" }));
    expect(await screen.findByTestId("transfer-option")).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: /Aprobar/ }));
    await waitFor(() => expect(recordDecision).toHaveBeenCalledWith("c1", { issue_id: transfer.issue_id, option_id: "a899c3d5698f", approved: true }, expect.anything()));
  });
});

describe("transfer alerts", () => {
  it("renders a transfer_opportunity alert with its Spanish title and the swap icon", () => {
    const alert = { alert_id: "t1", alert_type: 30, store_id: "S001", case_id: "x", severity_usd: 20.9, state: "nueva", as_of: "2026-07-19", category: "operacion", agent_id: "supply", ts: "2026-07-19T07:00:00Z", issue: { kind: "transfer_opportunity" } };
    const [w] = buildWarnings({ alerts: [alert as never], integrity: [] });
    expect(w).toMatchObject({ title: "Oportunidad de traslado", icon: "swap_horiz" });
  });
});
