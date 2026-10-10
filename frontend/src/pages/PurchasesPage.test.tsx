import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { fakeApi, renderPage } from "../test/helpers";
import PurchasesPage from "./PurchasesPage";

const open = (api = fakeApi()) =>
  renderPage(api, "/stores/S030/purchases", "/stores/:storeId/purchases", <PurchasesPage />);

describe("PurchasesPage", () => {
  it("groups lines by supplier", async () => {
    open();
    const g1 = await screen.findByTestId("supplier-SUP1");
    expect(within(g1).getByText("Panificadora Norte")).toBeInTheDocument();
    expect(within(g1).getByTestId("line-DONUT-GLZ")).toBeInTheDocument();
    expect(within(screen.getByTestId("supplier-SUP2")).getByTestId("line-MUFFIN")).toBeInTheDocument();
  });

  it("highlights deadlines that are today or tomorrow (simulated date)", async () => {
    open();
    const line = await screen.findByTestId("line-DONUT-GLZ");
    expect(within(line).getByTestId("deadline")).toHaveClass("deadline-today");
    expect(within(line).getByTestId("deadline")).toHaveTextContent("hoy");
    expect(within(screen.getByTestId("line-MUFFIN")).getByTestId("deadline")).not.toHaveClass("deadline-today");
  });

  it("shows qty with range and case rounding, stockout, risk, service level", async () => {
    open();
    const line = await screen.findByTestId("line-DONUT-GLZ");
    expect(within(line).getByText(/48 pzas \(36–60\)/)).toBeInTheDocument();
    expect(within(line).getByText(/4 cajas de 12/)).toBeInTheDocument();
    expect(within(line).getByText(/2026-03-03/)).toBeInTheDocument();
    expect(within(line).getByText(/72%/)).toBeInTheDocument();
    expect(within(line).getByText(/95%/)).toBeInTheDocument();
  });

  it("explains the current practice", async () => {
    open();
    expect(await screen.findByText(/hoy recibes 1\.4× lo que vendes/)).toBeInTheDocument();
  });

  it("shows min_order_warning as a soft badge only when present", async () => {
    open();
    const line = await screen.findByTestId("line-DONUT-GLZ");
    expect(within(line).getByText("Pedido mínimo $200")).toHaveClass("badge-soft");
    expect(within(screen.getByTestId("line-MUFFIN")).queryByTestId("min-warning")).toBeNull();
  });

  it("renders the waste vs lost sales mini-bar", async () => {
    open();
    const bar = within(await screen.findByTestId("line-DONUT-GLZ")).getByTestId("minibar");
    expect(bar).toHaveTextContent("merma $20.00");
    expect(bar).toHaveTextContent("ventas perdidas $60.00");
  });

  it("opens the issue detail from a line", async () => {
    open();
    const line = await screen.findByTestId("line-DONUT-GLZ");
    await userEvent.click(within(line).getByRole("button", { name: "Ver opciones" }));
    expect(await screen.findByTestId("option-o-n3")).toBeInTheDocument();
    expect(within(screen.getByTestId("line-MUFFIN")).queryByRole("button", { name: "Ver opciones" })).toBeNull();
  });

  it("shows empty and error states", async () => {
    const { unmount } = open(fakeApi({ getOrderPlan: async () => ({ ...(await fakeApi().getOrderPlan("c1")), lines: [] }) }));
    expect(await screen.findByText("Sin pedidos sugeridos")).toBeInTheDocument();
    unmount();
    open(fakeApi({ getOrderPlan: async () => { throw new Error("plan caído"); } }));
    expect(await screen.findByRole("alert")).toHaveTextContent("plan caído");
  });
});

describe("PurchasesPage with the live order-plan shape", () => {
  it("renders range waste/lost sales and an object min-order warning without crashing", async () => {
    const { planLive } = await import("../test/fixtures");
    renderPage(fakeApi({ getOrderPlan: async () => planLive }), "/stores/S030/purchases", "/stores/:storeId/purchases", <PurchasesPage />);
    expect(await screen.findByTestId("line-SKU-1")).toBeInTheDocument();
    expect(screen.getByTestId("min-warning")).toHaveTextContent("$106.10");
  });
});
