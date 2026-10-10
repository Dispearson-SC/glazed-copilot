import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fakeApi, renderPage } from "../test/helpers";
import CasesPage from "./CasesPage";

const open = (api = fakeApi()) => renderPage(api, "/cases", "/cases", <CasesPage />);

describe("CasesPage", () => {
  afterEach(() => vi.useRealTimers());

  it("lists cases of the selected store", async () => {
    const api = fakeApi();
    open(api);
    expect(await screen.findByText("Caso uno")).toBeInTheDocument();
    expect(api.listCases).toHaveBeenCalledWith({ store_id: "S030" });
  });

  it("defaults the simulated date to the pinned default", async () => {
    open();
    await screen.findByText("Caso uno");
    expect(screen.getByLabelText("Fecha simulada")).toHaveValue("2026-07-19");
  });

  it("creates a case with the form values", async () => {
    const api = fakeApi();
    open(api);
    await screen.findByText("Caso uno");
    await userEvent.clear(screen.getByLabelText("Fecha simulada"));
    await userEvent.type(screen.getByLabelText("Fecha simulada"), "2026-03-05");
    await userEvent.type(screen.getByLabelText("Título"), "Prueba");
    await userEvent.click(screen.getByRole("button", { name: "Crear caso" }));
    expect(api.createCase).toHaveBeenCalledWith({
      store_id: "S030", sim_today: "2026-03-05", mode: "live", title: "Prueba",
    });
    await waitFor(() => expect(api.listCases).toHaveBeenCalledTimes(2));
  });

  it("forks a case", async () => {
    const api = fakeApi();
    open(api);
    await userEvent.click(await screen.findByRole("button", { name: "Bifurcar" }));
    expect(api.forkCase).toHaveBeenCalledWith("c1", {});
  });

  it("asks a question and shows the reply when the turn finishes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const getTurn = vi
      .fn()
      .mockResolvedValueOnce({ turn_id: "t1", status: "pending" })
      .mockResolvedValue({ turn_id: "t1", status: "done", reply: "Ventas normales" });
    const api = fakeApi({ getTurn });
    open(api);
    await screen.findByText("Caso uno");
    await userEvent.type(screen.getByLabelText("Pregunta"), "¿cómo fue el día?");
    await userEvent.click(screen.getByRole("button", { name: "Preguntar" }));
    expect(api.sendMessage).toHaveBeenCalledWith("c1", "¿cómo fue el día?");
    expect(await screen.findByText(/Esperando respuesta/)).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(await screen.findByText("Ventas normales")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver traza" })).toHaveAttribute(
      "href", "/stores/S030/trace?case=c1&turn=t1",
    );
    const calls = getTurn.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(getTurn.mock.calls.length).toBe(calls);
  });

  it("shows a failed turn error", async () => {
    const api = fakeApi({ getTurn: vi.fn(async () => ({ turn_id: "t1", status: "failed", error: "sin llave LLM" })) });
    open(api);
    await screen.findByText("Caso uno");
    await userEvent.type(screen.getByLabelText("Pregunta"), "hola");
    await userEvent.click(screen.getByRole("button", { name: "Preguntar" }));
    expect(await screen.findByText(/sin llave LLM/)).toBeInTheDocument();
  });

  it("shows empty and error states", async () => {
    open(fakeApi({ listCases: vi.fn(async () => []) }));
    expect(await screen.findByText("Sin casos")).toBeInTheDocument();
  });

  it("shows an error when the backend is down", async () => {
    open(fakeApi({ listStores: vi.fn(async () => { throw new Error("caído"); }) }));
    expect(await screen.findByRole("alert")).toHaveTextContent("caído");
  });
});
