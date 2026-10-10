import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ev, fakeApi, renderPage } from "../test/helpers";
import TracePage from "./TracePage";

const events = [
  ev("2026-03-01T10:00:02Z", "present", "orchestrator", "tool_result", { tool: "kpis" }),
  ev("2026-03-01T10:00:00Z", "manager", "orchestrator", "message", { text: "¿cómo vamos?" }),
  ev("2026-03-01T10:00:01Z", "orchestrator", "present", "tool_call", { tool: "kpis" }),
];

const open = (api = fakeApi({ getTrace: vi.fn(async () => events) }), search = "") =>
  renderPage(api, `/stores/S030/trace${search}`, "/stores/:storeId/trace", <TracePage />);

describe("TracePage", () => {
  afterEach(() => vi.useRealTimers());

  it("shows the store by its display name, not its code", async () => {
    open();
    expect(await screen.findByRole("heading", { name: /Aeropuerto Norte · Glazed Centro/ })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /S030/ })).toBeNull();
  });

  it("lists the store's cases and loads the trace of the first", async () => {
    const api = fakeApi({ getTrace: vi.fn(async () => events) });
    open(api);
    await screen.findByTestId("bubble-0");
    expect(api.listCases).toHaveBeenCalledWith({ store_id: "S030" });
    expect(api.getTrace).toHaveBeenCalledWith("S030", "c1");
  });

  it("renders the timeline chronologically with from -> to and kind", async () => {
    open();
    const first = await screen.findByTestId("bubble-0");
    expect(first).toHaveTextContent("manager");
    expect(first).toHaveTextContent("orchestrator");
    expect(first).toHaveTextContent("message");
    expect(screen.getByTestId("bubble-1")).toHaveTextContent("tool_call");
    expect(screen.getByTestId("bubble-2")).toHaveTextContent("tool_result");
  });

  it("expands a payload on demand", async () => {
    open();
    const first = await screen.findByTestId("bubble-0");
    expect(within(first).getByText("¿cómo vamos?")).toBeInTheDocument();
    await userEvent.click(within(first).getByRole("button", { name: "Ver payload" }));
    expect(within(first).getByText(/"text": "¿cómo vamos\?"/)).toBeInTheDocument();
  });

  it("renders one lane per agent, highlighting the orchestrator", async () => {
    open();
    await screen.findByTestId("bubble-0");
    const orch = screen.getByTestId("lane-orchestrator");
    expect(orch).toHaveClass("orchestrator");
    expect(within(orch).getAllByTestId(/^lane-item/)).toHaveLength(3);
    expect(within(screen.getByTestId("lane-present")).getAllByTestId(/^lane-item/)).toHaveLength(2);
    expect(within(screen.getByTestId("lane-supply")).queryAllByTestId(/^lane-item/)).toHaveLength(0);
    expect(screen.getAllByTestId(/^lane-(?!item)/)).toHaveLength(8);
  });

  it("polls every 3s while the turn is pending and stops when done", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const getTurn = vi
      .fn()
      .mockResolvedValueOnce({ turn_id: "t1", status: "pending" })
      .mockResolvedValue({ turn_id: "t1", status: "done", reply: "ok" });
    const getTrace = vi.fn(async () => events);
    open(fakeApi({ getTurn, getTrace }), "?turn=t1");
    await screen.findByTestId("bubble-0");
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    await waitFor(() => expect(getTurn).toHaveBeenCalledTimes(2));
    await screen.findByText(/Turno terminado/);
    await userEvent.click(screen.getByRole("checkbox", { name: "En vivo" }));
    const after = getTrace.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    expect(getTrace.mock.calls.length).toBe(after);
    expect(getTurn).toHaveBeenCalledTimes(2);
  });

  it("shows empty and error states", async () => {
    open(fakeApi({ getTrace: vi.fn(async () => []) }));
    expect(await screen.findByText("Sin eventos todavía")).toBeInTheDocument();
  });

  it("shows an error when the backend is down", async () => {
    open(fakeApi({ listCases: vi.fn(async () => { throw new Error("caído"); }) }));
    expect(await screen.findByRole("alert")).toHaveTextContent("caído");
  });

  it("preselects the case from the query string", async () => {
    const api = fakeApi({
      listCases: vi.fn(async () => [
        { ...(await fakeApi().listCases({})) [0], case_id: "c1" },
        { ...(await fakeApi().listCases({})) [0], case_id: "c9", title: "otro" },
      ]),
      getTrace: vi.fn(async () => events),
    });
    open(api, "?case=c9");
    await waitFor(() => expect(api.getTrace).toHaveBeenCalledWith("S030", "c9"));
  });

  it("live toggle is ON by default and polls the trace every 3s until switched off", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const getTrace = vi.fn(async () => events);
    open(fakeApi({ getTrace }));
    await screen.findByTestId("bubble-0");
    const toggle = screen.getByRole("checkbox", { name: "En vivo" });
    expect(toggle).toBeChecked();
    const n = getTrace.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(3100); });
    expect(getTrace.mock.calls.length).toBeGreaterThan(n);
    await userEvent.click(toggle);
    const m = getTrace.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(9000); });
    expect(getTrace.mock.calls.length).toBe(m);
  });

  it("lists the newest cases first", async () => {
    const base = (await fakeApi().listCases({}))[0];
    const api = fakeApi({
      listCases: vi.fn(async () => [
        { ...base, case_id: "old", title: "stress-old", created_at: "2026-03-01T08:00:00Z" },
        { ...base, case_id: "new", title: "stress-new", created_at: "2026-03-02T08:00:00Z" },
      ]),
      getTrace: vi.fn(async () => events),
    });
    open(api);
    await waitFor(() => expect(api.getTrace).toHaveBeenCalledWith("S030", "new"));
    const opts = screen.getAllByRole("option").map((o) => o.textContent ?? "");
    expect(opts[0]).toContain("stress-new");
    expect(opts[1]).toContain("stress-old");
  });
});
