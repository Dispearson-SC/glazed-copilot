import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { caseA, fakeApi, renderPage } from "../../test/helpers";
import CopilotPage from "../../pages/CopilotPage";

const mk = (id: string, created: string, over = {}) => ({ ...caseA, case_id: id, sim_today: "2026-07-19", title: `Título ${id}`, created_at: created, issue_key: null, archived: false, ...over });
const base = mk("c1", "2026-07-19T08:00:00Z");
const c2 = mk("c2", "2026-07-19T09:00:00Z", { title: "Conversación 09:00" });
const c3 = mk("c3", "2026-07-19T10:00:00Z", { title: "Conversación 10:00" });
const hidden = [
  mk("x1", "2026-07-19T11:00:00Z", { archived: true, title: "Archivada" }),
  mk("x2", "2026-07-19T11:30:00Z", { issue_key: "S030|stockout_risk|SKU-1", title: "De un issue" }),
  mk("x3", "2026-07-18T11:30:00Z", { sim_today: "2026-07-18", title: "Otro día" }),
];

const turn = (text: string) => ({ turn_id: "t", ts: "2026-07-19T09:00:00Z", user_text: text, reply: "ok", status: "done" });

const open = (over = {}) =>
  renderPage(
    fakeApi({ listCases: vi.fn(async () => [base, c2, c3, ...hidden]), listTurns: vi.fn(async (id: string) => (id === "c2" ? [turn("¿Qué pido hoy?")] : id === "c3" ? [turn("Resume mermas")] : [])), ...over }),
    "/copiloto", "/copiloto", <CopilotPage />,
  );

describe("Conversaciones (Agente)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("Nueva conversación creates a live case for the same store and date, then switches to it", async () => {
    const created = mk("c9", "2026-07-19T12:00:00Z");
    let all = [base, c2, c3];
    const createCase = vi.fn(async () => { all = [...all, created]; return created; });
    const listTurns = vi.fn(async () => []);
    open({ createCase, listTurns, listCases: vi.fn(async () => all) });
    await userEvent.click(await screen.findByRole("button", { name: "Nueva conversación" }));
    await waitFor(() =>
      expect(createCase).toHaveBeenCalledWith({ store_id: "S030", sim_today: "2026-07-19", mode: "live", title: expect.stringMatching(/^Conversación \d\d:\d\d$/) }),
    );
    await waitFor(() => expect(localStorage.getItem("glazed.caseId.S030")).toBe("c9"));
    await waitFor(() => expect(listTurns).toHaveBeenCalledWith("c9"));
  });

  it("lists earlier conversations of the same store and date, newest first, without archived or issue cases", async () => {
    open();
    await userEvent.click(await screen.findByRole("button", { name: "Conversaciones anteriores" }));
    const sheet = await screen.findByRole("dialog", { name: "Conversaciones anteriores" });
    // Rendered at <body> level (portal) and centred, never inside the fixed top bar.
    expect(sheet.closest("header")).toBeNull();
    expect(sheet.parentElement?.className).toContain("items-center");
    const rows = within(sheet).getAllByRole("button", { name: /^Abrir conversación/ });
    expect(rows.map((r) => r.getAttribute("data-case"))).toEqual(["c3", "c2", "c1"]);
    expect(within(sheet).queryByText("Archivada")).toBeNull();
    expect(within(sheet).queryByText("De un issue")).toBeNull();
    expect(within(sheet).queryByText("Otro día")).toBeNull();
  });

  it("shows the first user message as preview, fetched on open", async () => {
    const listTurns = vi.fn(async (id: string) => (id === "c3" ? [turn("Resume mermas")] : []));
    open({ listTurns });
    await screen.findByRole("button", { name: "Conversaciones anteriores" });
    const before = listTurns.mock.calls.filter((c) => c[0] === "c2").length;
    await userEvent.click(screen.getByRole("button", { name: "Conversaciones anteriores" }));
    expect(await screen.findByText("Resume mermas")).toBeInTheDocument();
    expect(listTurns.mock.calls.filter((c) => c[0] === "c3").length).toBeGreaterThan(0);
    expect(before).toBe(0);
  });

  it("selecting one switches the active case, closes the sheet and remembers it per store", async () => {
    const listTurns = vi.fn(async (id: string) => (id === "c2" ? [turn("¿Qué pido hoy?")] : []));
    open({ listTurns });
    await userEvent.click(await screen.findByRole("button", { name: "Conversaciones anteriores" }));
    await userEvent.click(await screen.findByRole("button", { name: /Abrir conversación.*Conversación 09:00/ }));
    expect(screen.queryByRole("dialog", { name: "Conversaciones anteriores" })).toBeNull();
    expect(localStorage.getItem("glazed.caseId.S030")).toBe("c2");
    await waitFor(() => expect(listTurns).toHaveBeenCalledWith("c2"));
  });

  it("restores the last chosen case of the store", async () => {
    localStorage.setItem("glazed.caseId.S030", "c3");
    const listTurns = vi.fn(async () => []);
    open({ listTurns });
    await waitFor(() => expect(listTurns).toHaveBeenCalledWith("c3"));
  });

  it("survives localStorage throwing", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("denied"); });
    const listTurns = vi.fn(async () => []);
    open({ listTurns });
    await userEvent.click(await screen.findByRole("button", { name: "Conversaciones anteriores" }));
    await userEvent.click(await screen.findByRole("button", { name: /Abrir conversación.*Conversación 09:00/ }));
    expect(screen.queryByRole("dialog", { name: "Conversaciones anteriores" })).toBeNull();
    await waitFor(() => expect(listTurns).toHaveBeenCalledWith("c2"));
  });
});
