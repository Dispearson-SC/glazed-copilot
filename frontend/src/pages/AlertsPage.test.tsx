import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api";
import { alertA, proposalA, fakeApi, renderPage } from "../test/helpers";
import AlertsPage from "./AlertsPage";

const open = (api = fakeApi()) => renderPage(api, "/alerts", "/alerts", <AlertsPage />);

describe("AlertsPage", () => {
  afterEach(() => vi.useRealTimers());

  it("loads stores and lists alerts of the first store", async () => {
    const api = fakeApi();
    open(api);
    const row = await screen.findByTestId("alert-a1");
    expect(within(row).getByText(/123\.50/)).toBeInTheDocument();
    expect(within(row).getByText("nueva")).toHaveClass("badge");
    expect(within(row).getByText("Quiebre")).toBeInTheDocument(); // alert type
    expect(api.listAlerts).toHaveBeenCalledWith({ store_id: "S030" });
  });

  it("offers stores by display name, not by code", async () => {
    open();
    await screen.findByTestId("alert-a1");
    expect(screen.getByRole("option", { name: "Aeropuerto Norte · Glazed Centro" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /S030/ })).toBeNull();
  });

  it("reloads alerts when the store changes", async () => {
    const api = fakeApi();
    open(api);
    await screen.findByTestId("alert-a1");
    await userEvent.selectOptions(screen.getByLabelText("Sucursal"), "S031");
    await waitFor(() => expect(api.listAlerts).toHaveBeenLastCalledWith({ store_id: "S031" }));
  });

  it("marks an alert as seen and refreshes", async () => {
    const api = fakeApi();
    open(api);
    const row = await screen.findByTestId("alert-a1");
    await userEvent.click(within(row).getByRole("button", { name: "Marcar vista" }));
    expect(api.setAlertState).toHaveBeenCalledWith("a1", "vista");
    await waitFor(() => expect(api.listAlerts).toHaveBeenCalledTimes(2));
  });

  it("opens a detail panel with the issue payload and pending proposals", async () => {
    const api = fakeApi();
    open(api);
    await userEvent.click(await screen.findByText("Ver detalle"));
    const panel = await screen.findByRole("complementary", { name: "Detalle de alerta" });
    expect(within(panel).getByText(/stockout_risk/)).toBeInTheDocument();
    expect(api.listProposals).toHaveBeenCalledWith({ case_id: "c1", status: "pending" });
    expect(await within(panel).findByText(/place_order/)).toBeInTheDocument();
    expect(within(panel).getByText(/Evitar quiebre/)).toBeInTheDocument();
  });

  it("approves a proposal", async () => {
    const api = fakeApi();
    open(api);
    await userEvent.click(await screen.findByText("Ver detalle"));
    await userEvent.click(await screen.findByRole("button", { name: "Aprobar" }));
    expect(api.decide).toHaveBeenCalledWith("p1", { approved: true });
  });

  it("requires a reason to reject and submits it", async () => {
    const api = fakeApi();
    open(api);
    await userEvent.click(await screen.findByText("Ver detalle"));
    const reject = await screen.findByRole("button", { name: "Rechazar" });
    await userEvent.click(reject);
    expect(api.decide).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText("Motivo"), "sin presupuesto");
    await userEvent.click(reject);
    expect(api.decide).toHaveBeenCalledWith("p1", { approved: false, reason: "sin presupuesto" });
  });

  it("auto-refreshes every 10 seconds", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const api = fakeApi();
    open(api);
    await screen.findByTestId("alert-a1");
    const before = (api.listAlerts as ReturnType<typeof vi.fn>).mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect((api.listAlerts as ReturnType<typeof vi.fn>).mock.calls.length).toBeGreaterThan(before);
  });

  it("shows an error state when the backend is down", async () => {
    const down = vi.fn(async () => { throw new ApiError(0, "No se pudo conectar"); });
    open(fakeApi({ listStores: down }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo conectar");
  });

  it("shows an empty state when there are no alerts", async () => {
    open(fakeApi({ listAlerts: vi.fn(async () => []) }));
    expect(await screen.findByText("Sin alertas")).toBeInTheDocument();
  });

  it("shows the category and confidence Jev assigned to a rejection", async () => {
    const api = fakeApi({
      listProposals: vi.fn(async (q: { status?: string }) =>
        q.status === "rejected"
          ? [{ ...proposalA, status: "rejected", reason_category: "precio", reason_confidence: 0.81 }]
          : [proposalA]),
    });
    open(api);
    await userEvent.click(await screen.findByText("Ver detalle"));
    await userEvent.type(await screen.findByLabelText("Motivo"), "muy caro");
    await userEvent.click(screen.getByRole("button", { name: "Rechazar" }));
    expect(await screen.findByText(/Motivo clasificado: precio \(confianza 81%\)/)).toBeInTheDocument();
  });
});

describe("AlertsPage issue detail (Wave 5)", () => {
  it("renders option cards when the alert carries a full issue", async () => {
    const { issueA } = await import("../test/fixtures");
    const api = fakeApi({ listAlerts: async () => [{ ...alertA, issue: issueA }] });
    open(api);
    await userEvent.click(await screen.findByText("Ver detalle"));
    expect(await screen.findByTestId("option-o-n3")).toBeInTheDocument();
  });

  it("shows exposure instead of severity for integrity alerts and the Centinela label for type 21", async () => {
    const integ = { ...alertA, alert_id: "a9", alert_type: 9, issue: { kind: "orphan_sku", category: "integrity", exposure_usd: 777 } };
    const comp = { ...alertA, alert_id: "a21", alert_type: 21, issue: { kind: "compliance_deviation" } };
    open(fakeApi({ listAlerts: async () => [integ, comp] }));
    expect(await screen.findByText("Exposición $777.00")).toBeInTheDocument();
    expect(screen.getByText("Cumplimiento (Centinela)")).toBeInTheDocument();
    expect(screen.getByText("SKU huérfano")).toBeInTheDocument();
  });
});
