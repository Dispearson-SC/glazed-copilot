import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api";
import { orderPlanA, wasteIssue } from "../test/copilotFixtures";
import { fakeApi, renderPage } from "../test/helpers";
import CopilotPage from "./CopilotPage";

const apiWith = (over = {}) =>
  fakeApi({
    listProposals: vi.fn(async () => []),
    listIssues: vi.fn(async () => [wasteIssue]),
    getOrderPlan: vi.fn(async () => orderPlanA),
    ...over,
  });
const open = (api = apiWith()) => renderPage(api, "/copiloto", "/copiloto", <CopilotPage />);

async function openDecisiones(api = apiWith()) {
  open(api);
  await userEvent.click(await screen.findByRole("button", { name: /^Decisiones/ }));
  await screen.findByRole("heading", { name: "Decisiones de hoy" });
  return api;
}

describe("Decisiones window", () => {
  it("lists approvals and technical decisions from the real sources, with counts and capsule badge", async () => {
    await openDecisiones();
    expect(await screen.findByRole("heading", { name: "Omitir el pedido de 12 Croiss-Ant Donuts" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Comprar 1 caja de Md Choc Stout C.B. Wsweet Cold Foam" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Se necesita aprobación / opinión" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Decisiones técnicas" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Decisiones, 2 pendientes" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analizar con el copiloto" })).toBeInTheDocument();
    expect(screen.getByText("Summit Frozen Foods · llega mar 21 · $14.60")).toBeInTheDocument();
    expect(screen.getByText(/Pedido bajo el mínimo de \$300\.00/)).toBeInTheDocument();
  });

  it("shows empty states when nothing is pending", async () => {
    await openDecisiones(apiWith({ listIssues: async () => [], getOrderPlan: async () => ({ store_id: "S030", as_of: "x", total_lines: 0, lines: [] }) }));
    expect(await screen.findByText("Nada pendiente de tu opinión por ahora.")).toBeInTheDocument();
    expect(screen.getByText("Todas las decisiones técnicas de hoy están resueltas.")).toBeInTheDocument();
  });

  it("accepts a technical decision: propose, then decide, with idempotency keys; removes the card and toasts", async () => {
    const api = await openDecisiones();
    await userEvent.click(await screen.findByRole("button", { name: /Aceptar/ }));
    await waitFor(() => expect(api.decide).toHaveBeenCalled());
    expect(api.propose).toHaveBeenCalledWith(
      { case_id: "c1", issue_id: "S030|stockout_risk|SKU-100263", option_id: "8f63a675ef2b", rationale: expect.any(String) },
      { idempotencyKey: expect.any(String) },
    );
    expect(api.decide).toHaveBeenCalledWith("pp-new", { approved: true }, { idempotencyKey: expect.any(String) });
    expect(await screen.findByRole("status")).toHaveTextContent("Aceptada: Comprar 1 caja de Md Choc Stout C.B. Wsweet Cold Foam");
    expect(screen.queryByRole("heading", { name: /Comprar 1 caja/ })).toBeNull();
    expect(screen.getByText(/1 aceptada por ti/)).toBeInTheDocument();
  });

  it("reuses an existing pending proposal instead of proposing again", async () => {
    const pending = { proposal_id: "pp-old", case_id: "c1", store_id: "S030", issue_id: "S030|stockout_risk|SKU-100263", action_type: "place_order", params: {}, tier: "N2", rationale: "", status: "pending", reason: "", agent_id: "", created_at: "" };
    const api = await openDecisiones(apiWith({ listProposals: async () => [pending] }));
    await userEvent.click(await screen.findByRole("button", { name: /Aceptar/ }));
    await waitFor(() => expect(api.decide).toHaveBeenCalledWith("pp-old", { approved: true }, expect.anything()));
    expect(api.propose).not.toHaveBeenCalled();
  });

  it("keeps the card and shows the error when the backend refuses", async () => {
    await openDecisiones(apiWith({ propose: async () => { throw new ApiError(400, "unknown option"); } }));
    await userEvent.click(await screen.findByRole("button", { name: /Aceptar/ }));
    expect(await screen.findByRole("status")).toHaveTextContent("No se pudo registrar: unknown option");
    expect(screen.getByRole("heading", { name: /Comprar 1 caja/ })).toBeInTheDocument();
  });

  it("opens the reject sheet; the submit button needs a reason chip or text", async () => {
    const api = await openDecisiones();
    const card = (await screen.findByRole("heading", { name: /Comprar 1 caja/ })).closest("article")!;
    await userEvent.click(within(card).getByRole("button", { name: /Rechazar/ }));
    const sheet = screen.getByRole("dialog", { name: "Motivo del rechazo" });
    const submit = within(sheet).getByRole("button", { name: "Enviar motivo y rechazar" });
    expect(submit).toBeDisabled();
    await userEvent.click(within(sheet).getByRole("button", { name: "Precio o costo" }));
    expect(submit).toBeEnabled();
    await userEvent.type(within(sheet).getByLabelText("Cuéntale más (opcional)"), "muy caro");
    await userEvent.click(submit);
    await waitFor(() => expect(api.decide).toHaveBeenCalledWith("pp-new", { approved: false, reason: "Precio o costo: muy caro" }, expect.anything()));
    expect(await screen.findByRole("status")).toHaveTextContent("Motivo registrado como «Precio o costo»");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("heading", { name: /Comprar 1 caja/ })).toBeNull();
  });

  it("closes the sheet without deciding when the backdrop is pressed", async () => {
    const api = await openDecisiones();
    const card = (await screen.findByRole("heading", { name: /Comprar 1 caja/ })).closest("article")!;
    await userEvent.click(within(card).getByRole("button", { name: /Rechazar/ }));
    await userEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(api.decide).not.toHaveBeenCalled();
  });

  it("Analizar switches to Agente with the context pinned, the user message and the analysis card", async () => {
    const api = await openDecisiones();
    await userEvent.click(await screen.findByRole("button", { name: "Analizar con el copiloto" }));
    expect(await screen.findByText("Hablando de: Omitir el pedido de 12 Croiss-Ant Donuts")).toBeInTheDocument();
    expect(screen.getByText("Análisis")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Aprobar/ })).toBeInTheDocument();
    await waitFor(() => expect(api.sendMessage).toHaveBeenCalledWith("c1", expect.stringContaining("Contexto: Omitir el pedido de 12 Croiss-Ant Donuts")));
    expect(screen.getByText("Analiza: Omitir el pedido de 12 Croiss-Ant Donuts")).toBeInTheDocument();
  });

  it("the ⋯ menu offers 'Dialogar acerca de esta decisión' and opens the dialogue card", async () => {
    await openDecisiones();
    await userEvent.click(await screen.findByRole("button", { name: "Más opciones" }));
    await userEvent.click(screen.getByRole("menuitem", { name: /Dialogar acerca de esta decisión/ }));
    expect(await screen.findByText("Diálogo")).toBeInTheDocument();
    expect(screen.getByText("Por qué")).toBeInTheDocument();
  });

  it("approves from the analysis card", async () => {
    const api = await openDecisiones();
    await userEvent.click(await screen.findByRole("button", { name: "Analizar con el copiloto" }));
    await userEvent.click(await screen.findByRole("button", { name: /Aprobar/ }));
    await waitFor(() => expect(api.decide).toHaveBeenCalledWith("pp-new", { approved: true }, expect.anything()));
    expect(await screen.findByText("Decisión registrada")).toBeInTheDocument();
  });

  it("shows an order-plan line without issue read-only with 'Disponible pronto'", async () => {
    const line = { ...orderPlanA.lines[0], issue: null };
    await openDecisiones(apiWith({ listIssues: async () => [], getOrderPlan: async () => ({ ...orderPlanA, lines: [line] }) }));
    const card = (await screen.findByRole("heading", { name: /Comprar 10 pzas/ })).closest("article")!;
    expect(within(card).getByRole("button", { name: /Aceptar/ })).toBeDisabled();
    expect(within(card).getByText(/Disponible pronto/)).toBeInTheDocument();
  });
});
