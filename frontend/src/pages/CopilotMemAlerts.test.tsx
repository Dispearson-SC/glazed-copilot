import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { agentsA, alertsA, integrityA, memoriesA, pendingA } from "../test/copilotFixtures";
import { caseA, fakeApi, renderPage } from "../test/helpers";
import CopilotPage from "./CopilotPage";

const api = (over = {}) =>
  fakeApi({
    listCases: async () => [{ ...caseA, sim_today: "2026-07-19" }],
    listProposals: async () => [],
    getPending: async () => pendingA,
    listIssues: vi.fn(async (_c: string, q: { category?: string } = {}) => (q.category === "integrity" ? integrityA : [])),
    getMemories: vi.fn(async () => memoriesA),
    getAgentsStatus: async () => ({ connected: true, agents: agentsA }),
    listAlerts: vi.fn(async () => alertsA),
    ...over,
  });

async function open(tab: RegExp, a = api()) {
  renderPage(a, "/copiloto", "/copiloto", <CopilotPage />);
  await userEvent.click(await screen.findByRole("button", { name: tab }));
  return a;
}

describe("Memorias window", () => {
  it("lists the memories served by /memories with the design's filters, and the new ones are flagged", async () => {
    await open(/^Memorias/);
    expect(await screen.findByRole("heading", { name: "Memorias técnicas" })).toBeInTheDocument();
    expect(await screen.findByText(/Aprobaste omitir el pedido de 12 Croiss-Ant Donuts/)).toBeInTheDocument();
    expect(screen.getAllByText("Nuevo aprendizaje")).toHaveLength(1);
    expect(screen.getByText("3 casos · verificada")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { pressed: false }).map((b) => b.textContent)).toEqual(expect.arrayContaining(["Proveedores", "Demanda", "Eventos", "Preferencias"]));
    expect(screen.getByRole("button", { name: "Todas", pressed: true })).toBeInTheDocument();
  });

  it("filters by category and by search text", async () => {
    await open(/^Memorias/);
    await screen.findByText(/Aprobaste omitir/);
    await userEvent.click(screen.getByRole("button", { name: "Proveedores" }));
    expect(screen.queryByText(/Bacon Donuts/)).toBeNull();
    expect(screen.getByText(/Aprobaste omitir/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Todas" }));
    await userEvent.type(screen.getByRole("searchbox", { name: "Buscar una memoria" }), "bacon");
    expect(screen.getByText(/Bacon Donuts/)).toBeInTheDocument();
    expect(screen.queryByText(/Aprobaste omitir/)).toBeNull();
  });

  it("shows an honest empty state when nothing matches", async () => {
    await open(/^Memorias/);
    await userEvent.type(await screen.findByRole("searchbox", { name: "Buscar una memoria" }), "zzzz");
    expect(screen.getByText("Sin memorias que coincidan")).toBeInTheDocument();
  });

  it("says 'Disponible pronto' when the route answers 404 and the error otherwise", async () => {
    const { ApiError } = await import("../api");
    await open(/^Memorias/, api({ getMemories: async () => { throw new ApiError(404, "nf"); } }));
    expect(await screen.findByText("Disponible pronto")).toBeInTheDocument();
  });

  it("shows the error when the route fails", async () => {
    const { ApiError } = await import("../api");
    await open(/^Memorias/, api({ getMemories: async () => { throw new ApiError(500, "boom"); } }));
    expect(await screen.findByText("No se pudieron cargar las memorias.")).toBeInTheDocument();
  });

  it("badges the capsule with the memories created in the last 24 hours", async () => {
    renderPage(api(), "/copiloto", "/copiloto", <CopilotPage />);
    expect(await screen.findByRole("button", { name: "Memorias, 1 pendientes" })).toBeInTheDocument();
  });

  it("after a rejection it refetches /memories instead of adding a local entry", async () => {
    const created = { ...memoriesA[0], memory_id: "rej-new", text: "Rechazaste pedir 10 unidades: «Mal momento»", new: true };
    const getMemories = vi.fn().mockResolvedValueOnce(memoriesA.slice(1)).mockResolvedValue([created, ...memoriesA.slice(1)]);
    const a = api({ getMemories });
    renderPage(a, "/copiloto", "/copiloto", <CopilotPage />);
    await userEvent.click(await screen.findByRole("button", { name: /^Decisiones/ }));
    const card = (await screen.findByRole("heading", { name: /Pedir 10 unidades/ })).closest("article")!;
    await userEvent.click(within(card).getByRole("button", { name: /Rechazar/ }));
    await userEvent.click(screen.getByRole("button", { name: "Mal momento" }));
    await userEvent.click(screen.getByRole("button", { name: "Enviar motivo y rechazar" }));
    await vi.waitFor(() => expect(getMemories.mock.calls.length).toBeGreaterThan(1));
    await userEvent.click(screen.getByRole("button", { name: /^Memorias/ }));
    expect(await screen.findByText("Rechazaste pedir 10 unidades: «Mal momento»")).toBeInTheDocument();
    expect(screen.queryByText("Ajustará próximas propuestas")).toBeNull();
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

  it("has no Revertir button; Automáticas lists the alerts of the 'automatica' category with their agent", async () => {
    await open(/^Alertas/);
    await screen.findByText("Exceso de inventario: 12 Croiss-Ant Donuts");
    expect(screen.queryByRole("button", { name: "Revertir" })).toBeNull();
    expect(screen.getAllByText("Analista del presente").length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: "Automáticas" }));
    expect(screen.getByText("Acción aprobada sin ejecutar")).toBeInTheDocument();
    expect(screen.getByText("Centinela")).toBeInTheDocument();
    expect(screen.queryByText("Exceso de inventario: 12 Croiss-Ant Donuts")).toBeNull();
  });

  it("shows the empty state of Automáticas when no alert is automatic", async () => {
    await open(/^Alertas/, api({ listAlerts: async () => [alertsA[0]] }));
    await screen.findByText("Exceso de inventario: 12 Croiss-Ant Donuts");
    await userEvent.click(screen.getByRole("button", { name: "Automáticas" }));
    expect(screen.getByText(/Sin acciones automáticas todavía/)).toBeInTheDocument();
  });

  it("Preguntar opens the chat with the warning pinned and sends the plain question to the assistant (an alert is not an issue, so no issue context)", async () => {
    const a = await open(/^Alertas/);
    const card = (await screen.findByText("Exceso de inventario: 12 Croiss-Ant Donuts")).closest("article")!;
    await userEvent.click(within(card).getByRole("button", { name: /Preguntar/ }));
    expect(await screen.findByText("Hablando de: Exceso de inventario: 12 Croiss-Ant Donuts")).toBeInTheDocument();
    await vi.waitFor(() => expect(a.sendMessage).toHaveBeenCalledWith("c1", "Explícame: Exceso de inventario: 12 Croiss-Ant Donuts"));
    expect(screen.getByText("Explícame: Exceso de inventario: 12 Croiss-Ant Donuts")).toBeInTheDocument();
  });

  it("shows an empty state when there is nothing to warn about", async () => {
    await open(/^Alertas/, api({ listAlerts: async () => [], listIssues: async () => [] }));
    expect(await screen.findByText("Sin advertencias por ahora")).toBeInTheDocument();
  });
});
