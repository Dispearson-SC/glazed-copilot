import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ApiProvider } from "./ApiContext";
import { ApiError } from "./api";
import App from "./App";
import { SessionProvider } from "./SessionContext";
import { ev, fakeApi, proposalA } from "./test/helpers";

const open = (path: string, api = fakeApi()) =>
  render(
    <ApiProvider api={api}>
      <SessionProvider>
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      </SessionProvider>
    </ApiProvider>,
  );

/** Chat.dc.html, element by element. */
describe("Chat (/chat) matches Chat.dc.html", () => {
  it("header card: smart_toy icon, 'Chat del turno', subtitle and the agent badge", async () => {
    open("/chat");
    const header = await screen.findByTestId("chat-header");
    expect(within(header).getByText("smart_toy")).toBeInTheDocument();
    expect(within(header).getByRole("heading", { name: "Chat del turno" })).toBeInTheDocument();
    expect(within(header).getByText("Conversa con el asistente de barra")).toBeInTheDocument();
    expect(await within(header).findByTestId("chat-status")).toHaveTextContent("Sin agente");
  });

  it("the badge counts the connected agents when /agents/status answers", async () => {
    open("/chat", fakeApi({ getAgentsStatus: async () => ({ connected: true, agents: [{ agent_id: "a", display_name_es: "A", status: "up" }, { agent_id: "b", display_name_es: "B", status: "up" }] }) }));
    expect(await screen.findByText("2 agentes")).toBeInTheDocument();
  });

  it("top bar and bottom navigation as in the other screens", async () => {
    open("/chat");
    const bar = await screen.findByRole("banner");
    expect(within(bar).getByRole("button", { name: "Notificaciones" })).toBeInTheDocument();
    expect(within(bar).getByRole("link", { name: "Iniciar sesión" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Navegación principal" });
    expect(within(nav).getAllByRole("link").map((a) => a.textContent)).toEqual(["dashboardResumen", "receipt_longPedidos", "local_cafeProductos", "chatChat", "tuneAjustes"]);
    expect(within(nav).getByRole("link", { name: /Chat/ })).toHaveAttribute("aria-current", "page");
  });

  it("conversation box, the three design chips, composer and footer note", async () => {
    open("/chat");
    expect(await screen.findByRole("region", { name: "Conversación" })).toBeInTheDocument();
    for (const chip of ["¿Cómo van las ventas?", "Dame el ticket promedio", "¿Cuál es el favorito de hoy?"]) expect(screen.getByRole("button", { name: chip })).toBeInTheDocument();
    expect(screen.getByLabelText("Escribe un mensaje")).toHaveAttribute("placeholder", "Escribe un mensaje…");
    expect(screen.getByRole("button", { name: "Enviar mensaje" })).toBeDisabled();
    expect(screen.getByText("Interfaz lista. Conecta un agente para recibir respuestas.")).toBeInTheDocument();
  });

  it("a chip fills the draft (it does not send) and keeps showing after the conversation starts", async () => {
    const api = fakeApi();
    open("/chat", api);
    await userEvent.click(await screen.findByRole("button", { name: "Dame el ticket promedio" }));
    expect(screen.getByLabelText("Escribe un mensaje")).toHaveValue("Dame el ticket promedio");
    expect(api.sendMessage).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
    expect(await screen.findByText("listo")).toBeInTheDocument();
    expect(api.sendMessage).toHaveBeenCalledWith("c1", "Dame el ticket promedio");
    expect(screen.getByRole("button", { name: "¿Cómo van las ventas?" })).toBeInTheDocument();
  });

  it("shows the time under user and assistant bubbles", async () => {
    const api = fakeApi({ listTurns: async () => [{ turn_id: "t9", ts: "2026-03-01T10:00:00Z", user_text: "hola", reply: "buenas", status: "done" }] });
    open("/chat", api);
    expect(await screen.findByText("buenas")).toBeInTheDocument();
    expect(screen.getAllByText(/^\d{2}:\d{2}$/)).toHaveLength(2);
  });

  it("has none of the legacy elements: proposals, status text, metadata chips, steps", async () => {
    open("/chat", fakeApi({ getTurn: vi.fn(async () => ({ turn_id: "t1", status: "done", reply: "Pide 40", reply_meta: { source: "fast", elapsed_ms: 1500 } })) }));
    await userEvent.type(await screen.findByLabelText("Escribe un mensaje"), "hola");
    await userEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
    await screen.findByText("Pide 40");
    for (const legacy of [/Respuesta rápida/, /1\.5 s/, /Propuesta pendiente/, /Aprobar/, /Rechazar/, /En línea/, /Trabajando/, /Esperando respuesta/, /pasos intermedios/i, /Las propuestas pendientes/, /Copiloto/]) {
      expect(screen.queryByText(legacy)).toBeNull();
    }
    expect(screen.queryByRole("link", { name: /razonamiento/i })).toBeNull();
  });

  it("shows history from the trace and hides the internal events", async () => {
    const api = fakeApi({
      getTrace: vi.fn(async () => [
        ev("2026-03-01T10:00:00Z", "manager", "orchestrator", "message", { text: "¿cómo vamos?" }),
        ev("2026-03-01T10:00:02Z", "orchestrator", "manager", "message", { text: "Bien</think>" }),
        ev("2026-03-01T10:00:01Z", "orchestrator", "supply", "tool_call", { text: "oculto" }),
      ]),
    });
    open("/chat", api);
    expect(await screen.findByText("¿cómo vamos?")).toBeInTheDocument();
    expect(screen.getByText("Bien")).toBeInTheDocument();
    expect(screen.queryByText("oculto")).not.toBeInTheDocument();
  });

  it("shows an error bubble with retry when the turn fails", async () => {
    const getTurn = vi.fn().mockResolvedValue({ turn_id: "t1", status: "failed", error: "boom" });
    open("/chat", fakeApi({ getTurn }));
    await userEvent.type(await screen.findByLabelText("Escribe un mensaje"), "hola");
    await userEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
    expect(await screen.findByText(/boom/, undefined, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});

describe("floating chat on Main (Main.dc.html)", () => {
  it("opens a compact panel with two chips and the footer link, and sends a message", async () => {
    const api = fakeApi();
    open("/", api);
    await userEvent.click(await screen.findByRole("button", { name: "Abrir chat del turno" }));
    const panel = screen.getByRole("region", { name: "Chat flotante del turno" });
    expect(within(panel).getByRole("link", { name: "Abrir chat completo" })).toHaveAttribute("href", "/chat");
    expect(within(panel).queryByRole("button", { name: "¿Cuál es el favorito de hoy?" })).toBeNull();
    await userEvent.type(within(panel).getByLabelText("Escribe un mensaje"), "hola");
    await userEvent.click(within(panel).getByRole("button", { name: "Enviar mensaje" }));
    expect(await within(panel).findByText("listo")).toBeInTheDocument();
    expect(api.sendMessage).toHaveBeenCalledWith("c1", "hola");
  });

  it("uses the compact design: small send button and the link inside the footer block", async () => {
    open("/");
    await userEvent.click(await screen.findByRole("button", { name: "Abrir chat del turno" }));
    const panel = screen.getByRole("region", { name: "Chat flotante del turno" });
    const send = within(panel).getByRole("button", { name: "Enviar mensaje" });
    expect(send.className).toContain("w-10 h-10");
    expect(send.closest("form")!.parentElement!.contains(within(panel).getByRole("link", { name: "Abrir chat completo" }))).toBe(true);
  });

  it("the FAB toggles to a close icon and back", async () => {
    open("/");
    const fab = await screen.findByRole("button", { name: "Abrir chat del turno" });
    await userEvent.click(fab);
    expect(screen.getByRole("button", { name: "Cerrar chat del turno" })).toHaveAttribute("aria-expanded", "true");
  });
});

describe("assistant markdown", () => {
  const reply = [
    "## Pedidos de hoy",
    "",
    "Esto es **importante** y esto _no_.",
    "",
    "- uno",
    "- dos",
    "",
    "| SKU | Cant. |",
    "|---|---|",
    "| SKU-1 | 10 |",
    "| SKU-2 | 20 |",
    "",
    "<script>window.__pwned = true</script><b>html crudo</b>",
  ].join("\n");
  const ask = async (text: string) => {
    open("/chat", fakeApi({ getTurn: vi.fn(async () => ({ turn_id: "t1", status: "done", reply: text })) }));
    await userEvent.type(await screen.findByLabelText("Escribe un mensaje"), "pide");
    await userEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
  };

  it("renders bold, headings, lists and GFM tables, with the table scrolling inside the bubble", async () => {
    await ask(reply);
    expect(await screen.findByRole("heading", { name: "Pedidos de hoy" })).toBeInTheDocument();
    expect(screen.getByText("importante").tagName).toBe("STRONG");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((c) => c.textContent)).toEqual(["SKU", "Cant."]);
    expect(within(table).getByRole("cell", { name: "SKU-2" })).toBeInTheDocument();
    expect(table.parentElement!.className).toContain("overflow-x-auto");
    expect(screen.queryByText(/\*\*|\|---\|/)).toBeNull();
  });

  it("never renders raw HTML from a reply", async () => {
    await ask(reply);
    await screen.findByRole("table");
    expect(document.querySelector("script")).toBeNull();
    expect(document.querySelector("b")).toBeNull();
    expect((window as unknown as { __pwned?: boolean }).__pwned).toBeUndefined();
  });

  it("strips think markup before rendering", async () => {
    await ask("<think>secreto interno</think>Hola **equipo**");
    expect((await screen.findByText("equipo")).tagName).toBe("STRONG");
    expect(screen.queryByText(/secreto interno/)).toBeNull();
  });

  it("keeps the user's own text literal", async () => {
    open("/chat");
    await userEvent.type(await screen.findByLabelText("Escribe un mensaje"), "pide **x**");
    await userEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
    expect(await screen.findByText("pide **x**")).toBeInTheDocument();
  });
});

describe("chat page conversation box (Chat.dc.html)", () => {
  it("is a 320px box that scrolls instead of growing", async () => {
    open("/chat");
    const box = await screen.findByRole("region", { name: "Conversación" });
    expect(box.className).toMatch(/min-h-\[320px\]/);
    expect(box.className).toMatch(/max-h-\[320px\]/);
    expect(box.className).toMatch(/overflow-y-auto/);
  });
});
