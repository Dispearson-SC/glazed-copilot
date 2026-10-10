import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { expiringA, inventoryA } from "../test/fixtures";
import { fakeApi, renderPage } from "../test/helpers";
import InventoryPage from "./InventoryPage";

const ok = () => fakeApi({ getInventory: vi.fn(async () => inventoryA), getExpiring: async () => expiringA });
const open = (api = ok()) => renderPage(api, "/stores/S030/inventory", "/stores/:storeId/inventory", <InventoryPage />);

describe("InventoryPage", () => {
  it("shows the coverage line so partial inventory is never read as complete", async () => {
    open();
    expect(await screen.findByTestId("inventory-coverage")).toHaveTextContent("Inventario disponible para 89 de 127 productos");
  });

  it("lists days of cover, projected stockout and flags slow movers", async () => {
    open();
    const row = await screen.findByTestId("inv-SKU-1");
    expect(row).toHaveTextContent("Dona glaseada");
    expect(row).toHaveTextContent("2.0");
    expect(row).toHaveTextContent("2026-03-03");
    expect(row).not.toHaveTextContent("lento");
    expect(screen.getByTestId("inv-SKU-2")).toHaveTextContent("lento");
    expect(screen.getByTestId("inv-SKU-2")).toHaveTextContent("2026-02-10");
  });

  it("re-queries with the chosen sort", async () => {
    const api = ok();
    open(api);
    await screen.findByTestId("inv-SKU-1");
    await userEvent.click(screen.getByRole("button", { name: "Lentos" }));
    await waitFor(() => expect(api.getInventory).toHaveBeenLastCalledWith("c1", { sort: "slow", limit: "50" }));
  });

  it("shows expiring stock with waste as a range and the inferred lot age caveat", async () => {
    open();
    const e = await screen.findByTestId("expiring");
    expect(e).toHaveTextContent("Dona glaseada");
    expect(e).toHaveTextContent("8 pzas");
    expect(e).toHaveTextContent("2026-03-03");
    expect(e).toHaveTextContent("$4.00 – $16.00");
    expect(e).toHaveTextContent("edad del lote estimada");
    expect(screen.getByTestId("expiring-total")).toHaveTextContent("$4.00 – $16.00");
  });

  it("shows Disponible pronto per section, never an error, when routes are missing", async () => {
    open(fakeApi());
    await waitFor(() => expect(screen.getAllByTestId("soon")).toHaveLength(2));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByTestId("inventory-coverage")).toBeNull();
  });
});
