import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiProvider } from "../ApiContext";
import { SessionProvider, useSession } from "../SessionContext";
import { useCurrentCase } from "../useCurrentCase";
import { fakeApi, store, store2 } from "../test/helpers";
import StoreSwitcher, { storeClosedReason } from "./StoreSwitcher";

function Probe() {
  const s = useSession();
  const { currentCase } = useCurrentCase(s.storeId || "S030", s.refreshKey);
  return <output data-testid="probe">{`${s.storeId}|${s.caseId}|${s.refreshKey}|${currentCase?.case_id ?? ""}`}</output>;
}

function setup(api = fakeApi()) {
  render(
    <ApiProvider api={api}>
      <SessionProvider>
        <MemoryRouter>
          <StoreSwitcher><span>Nombre actual</span></StoreSwitcher>
          <Probe />
        </MemoryRouter>
      </SessionProvider>
    </ApiProvider>,
  );
  return api;
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("StoreSwitcher", () => {
  it("lists display names, never codes, and marks the current store", async () => {
    setup();
    await userEvent.click(screen.getByRole("button", { name: /cambiar sucursal/i }));
    const list = await screen.findByRole("dialog");
    expect(within(list).getByText(store.display_name!)).toBeInTheDocument();
    expect(within(list).getByText(store2.display_name!)).toBeInTheDocument();
    expect(within(list).queryByText(/S03[01]/)).toBeNull();
    const current = within(list).getByRole("button", { name: new RegExp(store.display_name!) });
    expect(current).toHaveAttribute("aria-current", "true");
  });

  it("filters by search, case-insensitive", async () => {
    setup();
    await userEvent.click(screen.getByRole("button", { name: /cambiar sucursal/i }));
    await screen.findByRole("dialog");
    await userEvent.type(screen.getByRole("searchbox"), "PLAZA sur");
    expect(screen.queryByText(store.display_name!)).toBeNull();
    expect(screen.getByText(store2.display_name!)).toBeInTheDocument();
  });

  it("choosing a store sets it, clears the case, bumps and lists that store's cases", async () => {
    const api = setup();
    await userEvent.click(screen.getByRole("button", { name: /cambiar sucursal/i }));
    await userEvent.click(await screen.findByRole("button", { name: new RegExp(store2.display_name!) }));
    await waitFor(() => expect(screen.getByTestId("probe").textContent).toMatch(/^S031\|\|1\|/));
    await waitFor(() => expect(api.listCases).toHaveBeenCalledWith({ store_id: "S031" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("closes on Escape and on backdrop tap", async () => {
    setup();
    await userEvent.click(screen.getByRole("button", { name: /cambiar sucursal/i }));
    await screen.findByRole("dialog");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /cambiar sucursal/i }));
    await userEvent.click(await screen.findByTestId("store-backdrop"));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("disables closed stores with the label Cerrada", async () => {
    const api = fakeApi({ listStores: vi.fn(async () => [store, { ...store2, closed_on: "2026-07-01" }]) });
    setup(api);
    await userEvent.click(screen.getByRole("button", { name: /cambiar sucursal/i }));
    const btn = await screen.findByRole("button", { name: new RegExp(store2.display_name!) });
    expect(btn).toBeDisabled();
    expect(within(btn).getByText("Cerrada")).toBeInTheDocument();
  });

  it("storeClosedReason honours closed_on and opened_on against the sim date", () => {
    expect(storeClosedReason(store)).toBe(false);
    expect(storeClosedReason({ ...store, closed_on: "2026-07-19" })).toBe(true);
    expect(storeClosedReason({ ...store, closed_on: "2026-07-20" })).toBe(false);
    expect(storeClosedReason({ ...store, opened_on: "2026-07-20" })).toBe(true);
  });
});

describe("persistence", () => {
  it("restores the stored store id", () => {
    localStorage.setItem("glazed.storeId", "S031");
    setup();
    expect(screen.getByTestId("probe").textContent).toMatch(/^S031\|/);
  });

  it("persists the chosen store", async () => {
    setup();
    await userEvent.click(screen.getByRole("button", { name: /cambiar sucursal/i }));
    await userEvent.click(await screen.findByRole("button", { name: new RegExp(store2.display_name!) }));
    expect(localStorage.getItem("glazed.storeId")).toBe("S031");
  });

  it("falls back to the first open store when the stored id is no longer in /stores", async () => {
    localStorage.setItem("glazed.storeId", "S999");
    setup();
    await waitFor(() => expect(screen.getByTestId("probe").textContent).toMatch(/^S030\|/));
    expect(localStorage.getItem("glazed.storeId")).toBe("S030");
  });

  it("falls back to the first open store when the stored one is closed", async () => {
    localStorage.setItem("glazed.storeId", "S030");
    setup(fakeApi({ listStores: vi.fn(async () => [{ ...store, closed_on: "2026-07-01" }, store2]) }));
    await waitFor(() => expect(screen.getByTestId("probe").textContent).toMatch(/^S031\|/));
  });

  it("falls back when the stored store is not yet open", async () => {
    localStorage.setItem("glazed.storeId", "S031");
    setup(fakeApi({ listStores: vi.fn(async () => [store, { ...store2, opened_on: "2026-12-01T00:00:00" }]) }));
    await waitFor(() => expect(screen.getByTestId("probe").textContent).toMatch(/^S030\|/));
  });

  it("compares only the YYYY-MM-DD part of the dates", () => {
    expect(storeClosedReason({ ...store, closed_on: "2026-07-19T10:00:00" })).toBe(true);
    expect(storeClosedReason({ ...store, opened_on: "2026-07-19T08:00:00" })).toBe(false);
    expect(storeClosedReason({ ...store, closed_on: "2026-07-20T00:00:00" })).toBe(false);
  });

  it("survives localStorage throwing", async () => {
    const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("denied"); });
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
    setup();
    await userEvent.click(screen.getByRole("button", { name: /cambiar sucursal/i }));
    await userEvent.click(await screen.findByRole("button", { name: new RegExp(store2.display_name!) }));
    await waitFor(() => expect(screen.getByTestId("probe").textContent).toMatch(/^S031\|/));
  });
});
