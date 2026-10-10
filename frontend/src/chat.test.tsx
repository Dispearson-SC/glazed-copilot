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

describe("chat route and nav", () => {
  it("adds a Chat entry to the bottom nav", async () => {
    open("/");
    expect(await screen.findByRole("link", { name: /Chat/ })).toHaveAttribute("href", "/chat");
  });

  it("serves the full chat at /chat with store name, sim date and suggestion chips", async () => {
    open("/chat");
    const header = await screen.findByTestId("chat-header");
    await within(header).findByText(/Aeropuerto Norte · Glazed Centro/);
    await vi.waitFor(() => expect(header).toHaveTextContent("2026-03-01"));
    expect(screen.getByRole("button", { name: "¿Qué tengo que pedir hoy?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "¿Qué alertas son urgentes?" })).toBeInTheDocument();
  });

  it("sends a chip question and shows the reply with a fast chip, without a reasoning link", async () => {
    const api = fakeApi({
      getTurn: vi.fn(async () => ({
        turn_id: "t1", status: "done", reply: "Pide 40", reply_meta: { source: "fast", elapsed_ms: 1500 },
      })),
    });
    open("/chat", api);
    await userEvent.click(await screen.findByRole("button", { name: "¿Qué tengo que pedir hoy?" }));
    await userEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
    expect(await screen.findByText("Pide 40")).toBeInTheDocument();
    expect(api.sendMessage).toHaveBeenCalledWith("c1", "¿Qué tengo que pedir hoy?");
    expect(screen.getByText("Respuesta rápida")).toBeInTheDocument();
    expect(screen.getByText(/1\.5 s/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /razonamiento/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "¿Qué tengo que pedir hoy?" })).not.toBeInTheDocument();
  });

  it("renders no chip when reply_meta is absent", async () => {
    open("/chat");
    await userEvent.type(await screen.findByLabelText("Escribe un mensaje"), "hola");
    await userEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
    await screen.findByText("listo");
    expect(screen.queryByText("Respuesta rápida")).not.toBeInTheDocument();
  });

  it("shows history from the trace", async () => {
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
    expect(screen.queryByRole("link", { name: /razonamiento/i })).not.toBeInTheDocument();
    expect(screen.queryByText("oculto")).not.toBeInTheDocument();
  });

  it("shows a truncation hint and collapsed intermediate steps for envelope history", async () => {
    const api = fakeApi({
      getTrace: vi.fn(async () => [
        ev("2026-03-01T10:00:00Z", "manager", "orchestrator", "message", { text: '{"kind": "request", "parts": [{"content": "¿Qué pido?"}]}' }),
        ev("2026-03-01T10:00:01Z", "orchestrator", "manager", "message", { text: '{"kind": "response", "parts": [{"content": "Consulto a abastecimiento…"}]}' }),
        ev("2026-03-01T10:00:02Z", "orchestrator", "manager", "message", { text: '{"kind": "response", "parts": [{"content": "Pide 40 y además' }),
      ]),
    });
    open("/chat", api);
    expect(await screen.findByText("Pide 40 y además")).toBeInTheDocument();
    expect(screen.getByText("…(recortado)")).toBeInTheDocument();
    expect(screen.getByText(/pasos intermedios/i)).toBeInTheDocument();
  });

  it("shows the working notice, then an error bubble with retry on failure", async () => {
    const getTurn = vi
      .fn()
      .mockResolvedValueOnce({ turn_id: "t1", status: "pending", still_running: true })
      .mockResolvedValue({ turn_id: "t1", status: "failed", error: "boom" });
    open("/chat", fakeApi({ getTurn }));
    await userEvent.type(await screen.findByLabelText("Escribe un mensaje"), "hola");
    await userEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
    expect(await screen.findByText(/El copiloto sigue trabajando/)).toBeInTheDocument();
    expect(await screen.findByText(/boom/, undefined, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});

describe("chat proposals", () => {
  const stateful = (over = {}) => {
    let list = [proposalA];
    return fakeApi({
      listProposals: vi.fn(async () => list),
      decide: vi.fn(async (id: string) => { list = list.filter((p) => p.proposal_id !== id); return {}; }),
      ...over,
    });
  };

  it("renders pending proposals inline on load and approves", async () => {
    const api = stateful();
    open("/chat", api);
    const card = await screen.findByTestId("proposal-p1");
    expect(card).toHaveTextContent("Evitar quiebre");
    await userEvent.click(within(card).getByRole("button", { name: "Aprobar" }));
    expect(api.decide).toHaveBeenCalledWith("p1", { approved: true }, { idempotencyKey: expect.any(String) });
    await vi.waitFor(() => expect(screen.queryByTestId("proposal-p1")).not.toBeInTheDocument());
  });

  it("shows proposals created during a turn that ends in done", async () => {
    let list: unknown[] = [];
    const api = fakeApi({
      listProposals: vi.fn(async () => list),
      getTurn: vi.fn(async () => { list = [proposalA]; return { turn_id: "t1", status: "done", reply: "Propuse un pedido" }; }),
    });
    open("/chat", api);
    await userEvent.type(await screen.findByLabelText("Escribe un mensaje"), "pide");
    await userEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
    expect(await screen.findByText("Propuse un pedido")).toBeInTheDocument();
    expect(await screen.findByTestId("proposal-p1")).toBeInTheDocument();
  });

  it("renders proposals on waiting_approval too", async () => {
    const api = stateful({ getTurn: vi.fn(async () => ({ turn_id: "t1", status: "waiting_approval" })) });
    open("/chat", api);
    await userEvent.type(await screen.findByLabelText("Escribe un mensaje"), "pide");
    await userEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
    expect(await screen.findByTestId("proposal-p1")).toBeInTheDocument();
  });

  it("requires a reason to reject", async () => {
    const api = stateful();
    open("/chat", api);
    const card = await screen.findByTestId("proposal-p1");
    await userEvent.click(within(card).getByRole("button", { name: "Rechazar" }));
    const confirm = within(card).getByRole("button", { name: "Confirmar rechazo" });
    expect(confirm).toBeDisabled();
    await userEvent.type(within(card).getByLabelText("Motivo del rechazo"), "muy caro");
    await userEvent.click(confirm);
    expect(api.decide).toHaveBeenCalledWith("p1", { approved: false, reason: "muy caro" }, { idempotencyKey: expect.any(String) });
  });

  it("does not show an error on 409", async () => {
    const api = fakeApi({
      listProposals: vi.fn().mockResolvedValueOnce([proposalA]).mockResolvedValue([]),
      decide: vi.fn().mockRejectedValue(new ApiError(409, "ya decidida")),
    });
    open("/chat", api);
    const card = await screen.findByTestId("proposal-p1");
    await userEvent.click(within(card).getByRole("button", { name: "Aprobar" }));
    await vi.waitFor(() => expect(screen.queryByTestId("proposal-p1")).not.toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("floating chat on the dashboard", () => {
  it("opens a compact panel from a bubble and links to the full chat", async () => {
    const api = fakeApi();
    open("/", api);
    await userEvent.click(await screen.findByRole("button", { name: "Abrir chat del turno" }));
    const panel = screen.getByRole("region", { name: "Chat flotante del turno" });
    expect(within(panel).getByRole("link", { name: "Abrir chat completo" })).toHaveAttribute("href", "/chat");
    await userEvent.type(within(panel).getByLabelText("Escribe un mensaje"), "hola");
    await userEvent.click(within(panel).getByRole("button", { name: "Enviar mensaje" }));
    expect(await within(panel).findByText("listo")).toBeInTheDocument();
    expect(api.sendMessage).toHaveBeenCalledWith("c1", "hola");
  });
});

describe("chat design parity", () => {
  it("full page: icon header card with a status badge and the design's conversation card", async () => {
    open("/chat");
    const header = await screen.findByTestId("chat-header");
    expect(within(header).getByText("smart_toy")).toBeInTheDocument();
    expect(within(header).getByRole("heading", { name: "Chat del turno" })).toBeInTheDocument();
    expect(within(header).getByTestId("chat-status")).toHaveTextContent("En línea");
    const conv = await screen.findByRole("region", { name: "Conversación" });
    expect(conv.className).toContain("rounded-[18px]");
    expect(conv.className).toContain("min-h-[320px]");
  });

  it("full page: status badge shows the copilot working while a turn runs", async () => {
    const getTurn = vi.fn(async () => ({ turn_id: "t1", status: "pending" as const }));
    open("/chat", fakeApi({ getTurn }));
    await userEvent.type(await screen.findByLabelText("Escribe un mensaje"), "hola");
    await userEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));
    expect(await screen.findByTestId("chat-status")).toHaveTextContent("Trabajando");
  });

  it("floating panel uses the compact design: two chips, small send button, link in the footer block", async () => {
    open("/");
    await userEvent.click(await screen.findByRole("button", { name: "Abrir chat del turno" }));
    const panel = screen.getByRole("region", { name: "Chat flotante del turno" });
    const chips = within(panel).getAllByRole("button").filter((b) => b.className.includes("font-label-md"));
    expect(chips).toHaveLength(2);
    const send = within(panel).getByRole("button", { name: "Enviar mensaje" });
    expect(send.className).toContain("w-10 h-10");
    const form = send.closest("form")!;
    expect(form.className).toContain("p-1.5 pl-4");
    expect(form.parentElement!.contains(within(panel).getByRole("link", { name: "Abrir chat completo" }))).toBe(true);
    expect(within(panel).getByText("smart_toy", { selector: "span.text-\\[18px\\]" })).toBeInTheDocument();
  });

  it("floating bubbles use the compact radius", async () => {
    open("/");
    await userEvent.click(await screen.findByRole("button", { name: "Abrir chat del turno" }));
    const panel = screen.getByRole("region", { name: "Chat flotante del turno" });
    await userEvent.type(within(panel).getByLabelText("Escribe un mensaje"), "hola");
    await userEvent.click(within(panel).getByRole("button", { name: "Enviar mensaje" }));
    const reply = await within(panel).findByText("listo");
    expect(reply.closest("[class*='rounded-[14px]']")).not.toBeNull();
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
