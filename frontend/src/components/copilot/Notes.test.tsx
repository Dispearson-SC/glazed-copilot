import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api";
import CopilotPage from "../../pages/CopilotPage";
import { memoriesA } from "../../test/copilotFixtures";
import { caseA, fakeApi, renderPage } from "../../test/helpers";

const open = async (over = {}) => {
  const api = fakeApi({ listCases: async () => [{ ...caseA, sim_today: "2026-07-19" }], getMemories: vi.fn(async () => memoriesA), ...over });
  renderPage(api, "/copiloto", "/copiloto", <CopilotPage />);
  await userEvent.click(await screen.findByRole("button", { name: /^Memorias/ }));
  await userEvent.click(await screen.findByRole("button", { name: "Anotar" }));
  return api;
};

describe("Manager notes (Anotar)", () => {
  it("opens a sheet with the text, the four categories and the optional dates and impact", async () => {
    await open();
    const sheet = screen.getByRole("dialog", { name: "Anotar una nota" });
    expect(sheet).toBeInTheDocument();
    for (const c of ["Eventos", "Demanda", "Proveedores", "Preferencias"]) expect(within(sheet).getByRole("button", { name: c })).toBeInTheDocument();
    expect(screen.getByLabelText("Nota")).toBeInTheDocument();
    expect(screen.getByLabelText("Desde (opcional)")).toBeInTheDocument();
    expect(screen.getByLabelText("Hasta (opcional)")).toBeInTheDocument();
    expect(screen.getByLabelText("Impacto esperado (opcional)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar nota" })).toBeDisabled();
  });

  it("posts the note, toasts and refetches /memories", async () => {
    const addNote = vi.fn(async () => ({ saved: true, memory_id: "note-1" }));
    const getMemories = vi.fn(async () => memoriesA);
    await open({ addNote, getMemories });
    const before = getMemories.mock.calls.length;
    await userEvent.type(screen.getByLabelText("Nota"), "Cierran la calle principal");
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Eventos" }));
    await userEvent.type(screen.getByLabelText("Impacto esperado (opcional)"), "-30%");
    await userEvent.click(screen.getByRole("button", { name: "Guardar nota" }));
    await waitFor(() => expect(addNote).toHaveBeenCalledWith("c1", { text: "Cierran la calle principal", category: "eventos", impact: "-30%" }));
    expect(await screen.findByText("Nota guardada")).toBeInTheDocument();
    await waitFor(() => expect(getMemories.mock.calls.length).toBeGreaterThan(before));
    expect(screen.queryByRole("dialog", { name: "Anotar una nota" })).toBeNull();
  });

  it("sends the dates when filled", async () => {
    const addNote = vi.fn(async () => ({ saved: true, memory_id: "n" }));
    await open({ addNote });
    await userEvent.type(screen.getByLabelText("Nota"), "Feria");
    await userEvent.type(screen.getByLabelText("Desde (opcional)"), "2026-07-20");
    await userEvent.type(screen.getByLabelText("Hasta (opcional)"), "2026-07-22");
    await userEvent.click(screen.getByRole("button", { name: "Guardar nota" }));
    await waitFor(() => expect(addNote).toHaveBeenCalledWith("c1", { text: "Feria", category: "eventos", date_from: "2026-07-20", date_to: "2026-07-22" }));
  });

  it("says 'Disponible pronto' when the route answers 404", async () => {
    await open({ addNote: async () => { throw new ApiError(404, "Not Found"); } });
    await userEvent.type(screen.getByLabelText("Nota"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Guardar nota" }));
    expect(await screen.findByText("Disponible pronto")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Anotar una nota" })).toBeInTheDocument();
  });

  it("shows other errors and keeps the text", async () => {
    await open({ addNote: async () => { throw new ApiError(500, "boom"); } });
    await userEvent.type(screen.getByLabelText("Nota"), "texto");
    await userEvent.click(screen.getByRole("button", { name: "Guardar nota" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
    expect(screen.getByLabelText("Nota")).toHaveValue("texto");
  });
});
