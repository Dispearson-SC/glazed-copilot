import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { caseA, fakeApi, renderPage } from "../test/helpers";
import DaySwitcher from "./DaySwitcher";

const open = (api = fakeApi()) => renderPage(api, "/", "/", <DaySwitcher storeId="S030" />);

describe("DaySwitcher", () => {
  it("shows the case date between two labelled buttons", async () => {
    open();
    expect(await screen.findByTestId("day-switcher-date")).toHaveTextContent("1 mar 2026");
    expect(screen.getByRole("button", { name: "Día anterior" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Día siguiente" })).toBeEnabled();
  });

  it("forward advances the case one day and toasts the outcomes", async () => {
    const advanceCase = vi.fn(async () => ({ sim_today: "2026-03-02", new_alerts: [], outcomes: [{}, {}] }));
    open(fakeApi({ advanceCase }));
    await userEvent.click(await screen.findByRole("button", { name: "Día siguiente" }));
    await waitFor(() => expect(advanceCase).toHaveBeenCalledWith("c1", { days: 1 }));
    expect(await screen.findByText("2 resultados de decisiones disponibles")).toBeInTheDocument();
  });

  it("forward shows no toast without outcomes", async () => {
    const advanceCase = vi.fn(async () => ({ sim_today: "2026-03-02", new_alerts: [], outcomes: [] }));
    open(fakeApi({ advanceCase }));
    await userEvent.click(await screen.findByRole("button", { name: "Día siguiente" }));
    await waitFor(() => expect(advanceCase).toHaveBeenCalled());
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("back switches to the existing case of the previous day", async () => {
    const today = { ...caseA, sim_today: "2026-07-19" };
    const prev = { ...caseA, case_id: "c0", sim_today: "2026-07-18", created_at: "2026-07-18T08:00:00Z" };
    const createCase = vi.fn(async () => prev);
    open(fakeApi({ listCases: async () => [today, prev], createCase }));
    await userEvent.click(await screen.findByRole("button", { name: "Día anterior" }));
    expect(await screen.findByTestId("day-switcher-date")).toHaveTextContent("18 jul 2026");
    expect(createCase).not.toHaveBeenCalled();
    expect(screen.getByText("Las decisiones de fechas posteriores no aparecen aquí")).toBeInTheDocument();
  });

  it("back creates the previous-day case when none exists", async () => {
    const today = { ...caseA, sim_today: "2026-07-19" };
    const created = { ...caseA, case_id: "c9", sim_today: "2026-07-18" };
    let cases = [today];
    const createCase = vi.fn(async () => { cases = [today, created]; return created; });
    open(fakeApi({ listCases: async () => cases, createCase }));
    await userEvent.click(await screen.findByRole("button", { name: "Día anterior" }));
    await waitFor(() => expect(createCase).toHaveBeenCalledWith({ store_id: "S030", sim_today: "2026-07-18", mode: "live", title: "Demo 2026-07-18" }));
    expect(await screen.findByTestId("day-switcher-date")).toHaveTextContent("18 jul 2026");
  });

  it("forward after back switches to the existing next-day case without advancing", async () => {
    const today = { ...caseA, case_id: "c1", sim_today: "2026-07-19", created_at: "2026-07-19T08:00:00Z" };
    const prev = { ...caseA, case_id: "c0", sim_today: "2026-07-18", created_at: "2026-07-18T08:00:00Z" };
    const advanceCase = vi.fn(async () => ({ sim_today: "2026-07-19", new_alerts: [], outcomes: [] }));
    const createCase = vi.fn(async () => prev);
    open(fakeApi({ listCases: async () => [today, prev], advanceCase, createCase }));
    await userEvent.click(await screen.findByRole("button", { name: "Día anterior" }));
    expect(await screen.findByTestId("day-switcher-date")).toHaveTextContent("18 jul 2026");
    await userEvent.click(screen.getByRole("button", { name: "Día siguiente" }));
    expect(await screen.findByTestId("day-switcher-date")).toHaveTextContent("19 jul 2026");
    expect(advanceCase).not.toHaveBeenCalled();
    expect(createCase).not.toHaveBeenCalled();
  });

  it("forward on the latest case advances exactly once", async () => {
    const advanceCase = vi.fn(async () => ({ sim_today: "2026-03-02", new_alerts: [], outcomes: [] }));
    const createCase = vi.fn(async () => caseA);
    open(fakeApi({ listCases: async () => [{ ...caseA, sim_today: "2026-07-19" }], advanceCase, createCase }));
    await userEvent.click(await screen.findByRole("button", { name: "Día siguiente" }));
    await waitFor(() => expect(advanceCase).toHaveBeenCalledTimes(1));
    expect(createCase).not.toHaveBeenCalled();
  });

  it("forward from an older case with no next-date case creates one instead of advancing the old case", async () => {
    const d17 = { ...caseA, case_id: "c17", sim_today: "2026-07-17", created_at: "2026-07-17T08:00:00Z" };
    const d19 = { ...caseA, case_id: "c19", sim_today: "2026-07-19", created_at: "2026-07-19T08:00:00Z" };
    const d18 = { ...caseA, case_id: "c18", sim_today: "2026-07-18", created_at: "2026-07-18T08:00:00Z" };
    let cases = [d17, d19];
    const advanceCase = vi.fn(async () => ({ sim_today: "x", new_alerts: [], outcomes: [] }));
    const createCase = vi.fn(async () => { cases = [d17, d18, d19]; return d18; });
    open(fakeApi({ listCases: async () => cases, advanceCase, createCase }));
    // The default pick is the live case at the default date (19); go back twice to reach 17.
    await userEvent.click(await screen.findByRole("button", { name: "Día anterior" }));
    await waitFor(() => expect(createCase).toHaveBeenCalledTimes(1));
    createCase.mockClear();
    cases = [d17, d19];
    await userEvent.click(await screen.findByRole("button", { name: "Día anterior" }));
    expect(await screen.findByTestId("day-switcher-date")).toHaveTextContent("17 jul 2026");
    await userEvent.click(screen.getByRole("button", { name: "Día siguiente" }));
    await waitFor(() => expect(createCase).toHaveBeenCalledWith({ store_id: "S030", sim_today: "2026-07-18", mode: "live", title: "Demo 2026-07-18" }));
    expect(advanceCase).not.toHaveBeenCalled();
    expect(createCase).toHaveBeenCalledTimes(1);
    expect(await screen.findByTestId("day-switcher-date")).toHaveTextContent("18 jul 2026");
  });

  it("disables both buttons while a request is in flight", async () => {
    let release!: () => void;
    const advanceCase = vi.fn(() => new Promise<{ sim_today: string; new_alerts: []; outcomes: [] }>((r) => { release = () => r({ sim_today: "x", new_alerts: [], outcomes: [] }); }));
    open(fakeApi({ advanceCase }));
    await userEvent.click(await screen.findByRole("button", { name: "Día siguiente" }));
    expect(screen.getByRole("button", { name: "Día anterior" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Día siguiente" })).toBeDisabled();
    release();
    await waitFor(() => expect(screen.getByRole("button", { name: "Día siguiente" })).toBeEnabled());
  });

  it("respects the dataset bounds", async () => {
    open(fakeApi({ listCases: async () => [{ ...caseA, sim_today: "2025-10-01" }] }));
    expect(await screen.findByRole("button", { name: "Día anterior" })).toBeDisabled();
  });

  it("disables forward at the last day", async () => {
    open(fakeApi({ listCases: async () => [{ ...caseA, sim_today: "2026-09-30" }] }));
    expect(await screen.findByRole("button", { name: "Día siguiente" })).toBeDisabled();
  });
});
