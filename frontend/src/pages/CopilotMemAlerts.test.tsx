import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { alertsA, historyA, integrityA, pendingA, suppliersA } from "../test/copilotFixtures";
import { caseA, fakeApi, renderPage } from "../test/helpers";
import CopilotPage from "./CopilotPage";

const api = (over = {}) =>
  fakeApi({
    listCases: async () => [{ ...caseA, sim_today: "2026-07-19" }],
    listProposals: async () => [],
    getPending: async () => pendingA,
    listIssues: vi.fn(async (_c: string, q: { category?: string } = {}) => (q.category === "integrity" ? integrityA : [])),
    getHistory: async () => historyA,
    getSupplierPerformance: async () => suppliersA,
    listAlerts: vi.fn(async () => alertsA),
    ...over,
  });

async function open(tab: RegExp, a = api()) {
  renderPage(a, "/copiloto", "/copiloto", <CopilotPage />);
  await userEvent.click(await screen.findByRole("button", { name: tab }));
  return a;
}

describe("Memorias window", () => {
  it("lists memories from the decision log and supplier performance, with the design's filters", async () => {
    await open(/^Memorias/);
    expect(await screen.findByRole("heading", { name: "Memorias técnicas" })).toBeInTheDocument();
    expect(await screen.findByText("«Prefiero quedarme corto»")).toBeInTheDocument();
    expect(screen.getByText(/Summit Frozen Foods: 90.1% a tiempo/)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { pressed: false }).map((b) => b.textContent)).toEqual(expect.arrayContaining(["Proveedores", "Demanda", "Eventos", "Preferencias"]));
    expect(screen.getByRole("button", { name: "Todas", pressed: true })).toBeInTheDocument();
  });

  it("filters by category and by search text", async () => {
    await open(/^Memorias/);
    await screen.findByText("«Prefiero quedarme corto»");
    await userEvent.click(screen.getByRole("button", { name: "Proveedores" }));
    expect(screen.queryByText("«Prefiero quedarme corto»")).toBeNull();
    expect(screen.getByText(/Summit/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Todas" }));
    await userEvent.type(screen.getByRole("searchbox", { name: "Buscar una memoria" }), "quedarme");
    expect(screen.getByText("«Prefiero quedarme corto»")).toBeInTheDocument();
    expect(screen.queryByText(/Summit/)).toBeNull();
  });

  it("shows an honest empty state when nothing matches", async () => {
    await open(/^Memorias/);
    await userEvent.type(await screen.findByRole("searchbox", { name: "Buscar una memoria" }), "zzzz");
    expect(screen.getByText("Sin memorias que coincidan")).toBeInTheDocument();
  });

  it("adds a 'Nuevo aprendizaje' memory only after a rejection was accepted by the backend", async () => {
    const a = api();
    renderPage(a, "/copiloto", "/copiloto", <CopilotPage />);
    await userEvent.click(await screen.findByRole("button", { name: /^Decisiones/ }));
    const card = (await screen.findByRole("heading", { name: /Pedir 10 unidades/ })).closest("article")!;
    await userEvent.click(within(card).getByRole("button", { name: /Rechazar/ }));
    await userEvent.click(screen.getByRole("button", { name: "Mal momento" }));
    await userEvent.click(screen.getByRole("button", { name: "Enviar motivo y rechazar" }));
    await screen.findByRole("status");
    expect(await screen.findByRole("button", { name: "Memorias, 1 pendientes" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^Memorias/ }));
    expect(await screen.findByText("Nuevo aprendizaje")).toBeInTheDocument();
    expect(screen.getByText("Motivo: Mal momento")).toBeInTheDocument();
  });
});

describe("Advertencias window", () => {
  it("lists open alerts and integrity issues in Spanish with the design's filters; the capsule shows the count", async () => {
    await open(/^Alertas/);
    expect(await screen.findByRole("heading", { name: "Advertencias" })).toBeInTheDocument();
    expect(await screen.findByText("Exceso de inventario: 12 Croiss-Ant Donuts")).toBeInTheDocument();
    expect(screen.getByText("Ventas sin producto en el catálogo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Alertas, 4 pendientes" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Datos e integridad" })).toBeInTheDocument();
  });

  it("filters by category", async () => {
    await open(/^Alertas/);
    await screen.findByText("Exceso de inventario: 12 Croiss-Ant Donuts");
    await userEvent.click(screen.getByRole("button", { name: "Datos e integridad" }));
    expect(screen.queryByText("Exceso de inventario: 12 Croiss-Ant Donuts")).toBeNull();
    expect(screen.getByText("Ventas sin producto en el catálogo")).toBeInTheDocument();
  });

  it("has no Revertir button and shows an empty state for Automáticas", async () => {
    await open(/^Alertas/);
    await screen.findByText("Exceso de inventario: 12 Croiss-Ant Donuts");
    expect(screen.queryByRole("button", { name: "Revertir" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Automáticas" }));
    expect(screen.getByText(/Sin acciones automáticas todavía/)).toBeInTheDocument();
  });

  it("Preguntar opens the chat with the warning pinned and sends it to the assistant with context", async () => {
    const a = await open(/^Alertas/);
    const card = (await screen.findByText("Exceso de inventario: 12 Croiss-Ant Donuts")).closest("article")!;
    await userEvent.click(within(card).getByRole("button", { name: /Preguntar/ }));
    expect(await screen.findByText("Hablando de: Exceso de inventario: 12 Croiss-Ant Donuts")).toBeInTheDocument();
    await vi.waitFor(() => expect(a.sendMessage).toHaveBeenCalledWith("c1", expect.stringContaining("Contexto: Exceso de inventario: 12 Croiss-Ant Donuts")));
    expect(screen.getByText("Explícame: Exceso de inventario: 12 Croiss-Ant Donuts")).toBeInTheDocument();
  });

  it("shows an empty state when there is nothing to warn about", async () => {
    await open(/^Alertas/, api({ listAlerts: async () => [], listIssues: async () => [] }));
    expect(await screen.findByText("Sin advertencias por ahora")).toBeInTheDocument();
  });
});
