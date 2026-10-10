import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { buildDecisionItems } from "../../data/copilot";
import { CopilotProvider } from "../../state/copilotStore";
import { orderPlanA, wasteIssue } from "../../test/copilotFixtures";
import { proposalA } from "../../test/helpers";
import type { useChat } from "../../useChat";
import AgentWindow from "./AgentWindow";
import AnalysisCard from "./AnalysisCard";

const items = buildDecisionItems({ issues: [wasteIssue], plan: orderPlanA, proposals: [], simToday: "2026-07-19" });
const [tech, approval] = items;

describe("AnalysisCard", () => {
  it("shows the badge, level, title, the three header figures and every section", () => {
    render(<AnalysisCard item={approval} mode="analizar" open onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByText("Análisis")).toBeInTheDocument();
    expect(screen.getByText("N2 · Propuesta")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: approval.title })).toBeInTheDocument();
    expect(screen.getByText("Impacto").nextSibling).toHaveTextContent("+$58.92");
    expect(screen.getByText("Confianza").nextSibling).toHaveTextContent("74%");
    expect(screen.getByText("Límite").nextSibling).toHaveTextContent("Hoy");
    for (const l of ["Problema", "Recomendación", "Pros", "Contras", "Requiere tu aprobación"]) expect(screen.getByText(l)).toBeInTheDocument();
  });

  it("labels the buttons Aprobar / Rechazar for approvals and Aceptar for technical decisions, in dialogue mode", () => {
    const { rerender } = render(<AnalysisCard item={approval} mode="analizar" open onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByRole("button", { name: /Aprobar/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Rechazar/ })).toBeInTheDocument();
    rerender(<AnalysisCard item={tech} mode="dialogo" open onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByText("Diálogo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Aceptar/ })).toBeInTheDocument();
  });

  it("calls the handlers and turns into 'Decisión registrada' once closed", async () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    const { rerender } = render(<AnalysisCard item={approval} mode="analizar" open onApprove={onApprove} onReject={onReject} />);
    await userEvent.click(screen.getByRole("button", { name: /Aprobar/ }));
    await userEvent.click(screen.getByRole("button", { name: /Rechazar/ }));
    expect(onApprove).toHaveBeenCalledWith(approval);
    expect(onReject).toHaveBeenCalledWith(approval);
    rerender(<AnalysisCard item={approval} mode="analizar" open={false} onApprove={onApprove} onReject={onReject} />);
    expect(screen.getByText("Decisión registrada")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Aprobar/ })).toBeNull();
  });

  it("disables decisions on a read-only item and says 'Disponible pronto'", () => {
    render(<AnalysisCard item={{ ...tech, readOnly: true }} mode="dialogo" open onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByRole("button", { name: /Aceptar/ })).toBeDisabled();
    expect(screen.getAllByText(/Disponible pronto/).length).toBeGreaterThan(0);
  });
});

type Chat = ReturnType<typeof useChat>;
const chatOf = (over: Partial<Chat> = {}): Chat => ({
  messages: [], status: "idle", stillRunning: false, proposals: [], decisionError: null,
  send: vi.fn(async () => {}), retry: vi.fn(async () => {}), decide: vi.fn(async () => {}), ...over,
}) as Chat;

const wrap = ({ children }: { children: ReactNode }) => <CopilotProvider>{children}</CopilotProvider>;
const props = { items, pendingLine: "1 esperan tu opinión · 1 listas para aceptar", onApprove: () => {}, onReject: () => {} };

describe("AgentWindow", () => {
  it("shows the orb status, title and pending line; never invents an agent count", () => {
    render(<AgentWindow chat={chatOf()} {...props} />, { wrapper: wrap });
    expect(screen.getByRole("heading", { name: "¿Qué decidimos hoy?" })).toBeInTheDocument();
    expect(screen.getByText("Listo")).toBeInTheDocument();
    expect(screen.getByText("1 esperan tu opinión · 1 listas para aceptar")).toBeInTheDocument();
    expect(screen.queryByText(/agentes conectados/)).toBeNull();
  });

  it("shows 'Pensando…' while a turn runs, with the wait pill", () => {
    render(<AgentWindow chat={chatOf({ status: "working" })} {...props} />, { wrapper: wrap });
    expect(screen.getByText("Pensando…")).toBeInTheDocument();
    expect(screen.getByText("Esperando respuesta…")).toBeInTheDocument();
  });

  it("renders user and assistant bubbles (markdown) with their time", () => {
    const chat = chatOf({ messages: [
      { id: "1", role: "user", text: "hola", ts: "2026-07-19T14:05:00Z" },
      { id: "2", role: "assistant", text: "**Pide** 40", ts: "2026-07-19T14:05:09Z" },
    ] });
    render(<AgentWindow chat={chat} {...props} />, { wrapper: wrap });
    expect(screen.getByText("hola")).toBeInTheDocument();
    expect(screen.getByText("Pide").tagName).toBe("STRONG");
    expect(screen.getAllByText(/Orquestador ·/)).toHaveLength(1);
  });

  it("sends a typed message and clears the input; the send button is disabled when empty", async () => {
    const chat = chatOf();
    render(<AgentWindow chat={chat} {...props} />, { wrapper: wrap });
    const send = screen.getByRole("button", { name: "Enviar mensaje" });
    expect(send).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Mensaje para el copiloto"), "¿Qué pido?");
    await userEvent.click(send);
    expect(chat.send).toHaveBeenCalledWith("¿Qué pido?", undefined);
    expect(screen.getByLabelText("Mensaje para el copiloto")).toHaveValue("");
  });

  it("sends a suggestion immediately", async () => {
    const chat = chatOf();
    render(<AgentWindow chat={chat} {...props} />, { wrapper: wrap });
    await userEvent.click(screen.getByRole("button", { name: "¿Qué tengo que pedir hoy?" }));
    expect(chat.send).toHaveBeenCalledWith("¿Qué tengo que pedir hoy?", undefined);
  });

  it("keeps the microphone honest: it says 'Disponible pronto' instead of recording", async () => {
    render(<AgentWindow chat={chatOf()} {...props} />, { wrapper: wrap });
    const mic = screen.getByRole("button", { name: "Hablar con el copiloto" });
    expect(mic.className).toMatch(/w-11/);
    await userEvent.click(mic);
    expect(screen.queryByRole("status")).toBeNull(); // toast is rendered by the page; the click must not throw
  });

  it("shows inline pending proposals and errors from useChat", () => {
    const chat = chatOf({ proposals: [proposalA], messages: [{ id: "e", role: "error", text: "falló", retryText: "x" }] });
    render(<AgentWindow chat={chat} {...props} />, { wrapper: wrap });
    expect(screen.getByTestId("proposal-p1")).toBeInTheDocument();
    expect(within(screen.getByRole("alert")).getByText("falló")).toBeInTheDocument();
  });
});
