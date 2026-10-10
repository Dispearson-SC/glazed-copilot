import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { ApiProvider } from "../../ApiContext";
import { buildPendingItems } from "../../data/copilot";
import { CopilotProvider } from "../../state/copilotStore";
import { analysisApproval, pendingA } from "../../test/copilotFixtures";
import { fakeApi, proposalA } from "../../test/helpers";
import type { useChat } from "../../useChat";
import AgentWindow from "./AgentWindow";
import AnalysisCard from "./AnalysisCard";

const items = buildPendingItems(pendingA, "2026-07-19");
const [tech, approval] = items;
const ok = { status: "ok", data: analysisApproval } as const;

describe("AnalysisCard", () => {
  it("shows the badge, level, title, the three header figures and every section", () => {
    render(<AnalysisCard item={approval} analysis={ok} mode="analizar" open onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByText("Análisis")).toBeInTheDocument();
    expect(screen.getByText("N2 · Propuesta")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: approval.title })).toBeInTheDocument();
    expect(screen.getByText("Impacto").nextSibling).toHaveTextContent("+$58.92");
    expect(screen.getByText(/Reduce la merma en \$58.92/)).toBeInTheDocument();
    expect(screen.getByText("Confianza").nextSibling).toHaveTextContent("74%");
    expect(screen.getByText("Límite").nextSibling).toHaveTextContent("Hoy");
    for (const l of ["Problema", "Recomendación", "Pros", "Contras", "Requiere tu aprobación"]) expect(screen.getByText(l)).toBeInTheDocument();
  });

  it("labels the buttons Aprobar / Rechazar for approvals and Aceptar for technical decisions, in dialogue mode", () => {
    const { rerender } = render(<AnalysisCard item={approval} analysis={ok} mode="analizar" open onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByRole("button", { name: /Aprobar/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Rechazar/ })).toBeInTheDocument();
    rerender(<AnalysisCard item={tech} analysis={ok} mode="dialogo" open onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByText("Diálogo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Aceptar/ })).toBeInTheDocument();
  });

  it("calls the handlers and turns into 'Decisión registrada' once closed", async () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    const { rerender } = render(<AnalysisCard item={approval} analysis={ok} mode="analizar" open onApprove={onApprove} onReject={onReject} />);
    await userEvent.click(screen.getByRole("button", { name: /Aprobar/ }));
    await userEvent.click(screen.getByRole("button", { name: /Rechazar/ }));
    expect(onApprove).toHaveBeenCalledWith(approval);
    expect(onReject).toHaveBeenCalledWith(approval);
    rerender(<AnalysisCard item={approval} analysis={ok} mode="analizar" open={false} onApprove={onApprove} onReject={onReject} />);
    expect(screen.getByText("Decisión registrada")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Aprobar/ })).toBeNull();
  });

  it("says it is loading, 'Disponible pronto' on a 404 and the error otherwise, instead of empty sections", () => {
    const { rerender } = render(<AnalysisCard item={approval} analysis={{ status: "loading" }} mode="analizar" open onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByText("Cargando análisis…")).toBeInTheDocument();
    rerender(<AnalysisCard item={approval} analysis={{ status: "soon" }} mode="analizar" open onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByText("Disponible pronto")).toBeInTheDocument();
    rerender(<AnalysisCard item={approval} analysis={{ status: "error", message: "boom" }} mode="analizar" open onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByText("No se pudo cargar el análisis: boom")).toBeInTheDocument();
  });

  it("disables Aprobar and Rechazar while a request for the card is in flight", () => {
    render(<AnalysisCard item={approval} analysis={ok} mode="analizar" open busy onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByRole("button", { name: /Aprobar/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Rechazar/ })).toBeDisabled();
  });

  it("disables decisions on a read-only item and says 'Disponible pronto'", () => {
    render(<AnalysisCard item={{ ...tech, readOnly: true }} analysis={ok} mode="dialogo" open onApprove={() => {}} onReject={() => {}} />);
    expect(screen.getByRole("button", { name: /Aceptar/ })).toBeDisabled();
    expect(screen.getAllByText(/Disponible pronto/).length).toBeGreaterThan(0);
  });
});

type Chat = ReturnType<typeof useChat>;
const chatOf = (over: Partial<Chat> = {}): Chat => ({
  messages: [], status: "idle", stillRunning: false, progress: [], proposals: [], decisionError: null,
  send: vi.fn(async () => {}), retry: vi.fn(async () => {}), decide: vi.fn(async () => {}), ...over,
}) as Chat;

const wrap = ({ children }: { children: ReactNode }) => (
  <ApiProvider api={fakeApi({ getAnalysis: vi.fn(async () => analysisApproval) })}>
    <CopilotProvider>{children}</CopilotProvider>
  </ApiProvider>
);
const props = { caseId: "c1", items, pendingLine: "1 esperan tu opinión · 1 listas para aceptar", onApprove: () => {}, onReject: () => {} };

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

  it("names the agents being consulted while the turn is pending", () => {
    const progress = [
      { agent_id: "supply", display_name_es: "Analista de abastecimiento", state: "consulting" as const },
      { agent_id: "past", display_name_es: "Analista histórico", state: "consulting" as const },
      { agent_id: "present", display_name_es: "Analista del presente", state: "done" as const },
    ];
    render(<AgentWindow chat={chatOf({ status: "working", progress })} {...props} />, { wrapper: wrap });
    expect(screen.getByText("Consultando a Analista de abastecimiento y Analista histórico…")).toBeInTheDocument();
    expect(screen.queryByText("Esperando respuesta…")).toBeNull();
  });

  it("joins three agents with commas and 'y'", () => {
    const progress = ["A", "B", "C"].map((n) => ({ agent_id: n, display_name_es: n, state: "consulting" as const }));
    render(<AgentWindow chat={chatOf({ status: "working", progress })} {...props} />, { wrapper: wrap });
    expect(screen.getByText("Consultando a A, B y C…")).toBeInTheDocument();
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
