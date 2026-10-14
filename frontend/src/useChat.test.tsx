import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { ApiProvider } from "./ApiContext";
import { ApiError } from "./api";
import { fakeApi, ev, proposalA } from "./test/helpers";
import { useChat } from "./useChat";

const OPTS = { storeId: "S030", pollMs: 5, notFoundGraceMs: 60 };
const wrap = (api: ReturnType<typeof fakeApi>) => ({ children }: { children: ReactNode }) => (
  <ApiProvider api={api}>{children}</ApiProvider>
);
const setup = (api: ReturnType<typeof fakeApi>, opts = OPTS) => renderHook(() => useChat("c1", opts), { wrapper: wrap(api) });

describe("useChat", () => {
  it("rebuilds history from the trace", async () => {
    const api = fakeApi({
      getTrace: vi.fn(async () => [
        ev("2026-03-01T10:00:00Z", "manager", "orchestrator", "message", { text: "hola" }),
        ev("2026-03-01T10:00:01Z", "orchestrator", "manager", "message", { text: "buenas" }),
      ]),
    });
    const { result } = setup(api);
    await waitFor(() => expect(result.current.messages).toHaveLength(2));
    expect(api.getTrace).toHaveBeenCalledWith("S030", "c1");
  });

  it("loads the history from the stored turns when the route exists, without reading the trace", async () => {
    const api = fakeApi({
      listTurns: vi.fn(async () => [{ turn_id: "t9", ts: "2026-03-01T10:00:00Z", user_text: "hola", reply: "buenas", status: "done" }]),
      getTrace: vi.fn(async () => []),
    });
    const { result } = setup(api);
    await waitFor(() => expect(result.current.messages).toHaveLength(2));
    expect(result.current.messages[1]).toMatchObject({ role: "assistant", text: "buenas", turnId: "t9" });
    expect(api.listTurns).toHaveBeenCalledWith("c1");
    expect(api.getTrace).not.toHaveBeenCalled();
  });

  it("falls back to the trace when the turns route answers an empty list", async () => {
    const api = fakeApi({
      listTurns: vi.fn(async () => []),
      getTrace: vi.fn(async () => [ev("2026-03-01T10:00:00Z", "manager", "orchestrator", "message", { text: "hola" })]),
    });
    const { result } = setup(api);
    await waitFor(() => expect(result.current.messages).toHaveLength(1));
  });

  it("falls back to the trace parser when the turns route answers 404", async () => {
    const api = fakeApi({
      listTurns: vi.fn(async () => { throw new ApiError(404, "nf"); }),
      getTrace: vi.fn(async () => [ev("2026-03-01T10:00:00Z", "manager", "orchestrator", "message", { text: "hola" })]),
    });
    const { result } = setup(api);
    await waitFor(() => expect(result.current.messages).toHaveLength(1));
    expect(api.getTrace).toHaveBeenCalledWith("S030", "c1");
  });

  describe("pending turns loaded from history", () => {
    const pendingTurn = { turn_id: "t7", ts: "2026-03-01T10:00:00Z", user_text: "hola", reply: null, status: "pending" as const };

    it("resumes polling and replaces the working bubble with the parsed reply, then loads proposals", async () => {
      const getTurn = vi
        .fn()
        .mockResolvedValueOnce({ turn_id: "t7", status: "pending", still_running: true })
        .mockResolvedValue({ turn_id: "t7", status: "done", reply: "Listo, ya quedó" });
      const listProposals = vi.fn(async () => [proposalA]);
      const api = fakeApi({ listTurns: vi.fn(async () => [pendingTurn]), getTurn, listProposals });
      const { result } = setup(api);
      await waitFor(() => expect(result.current.messages[1]?.text).toBe("Listo, ya quedó"));
      expect(getTurn).toHaveBeenCalledWith("c1", "t7");
      expect(getTurn.mock.calls.length).toBeGreaterThanOrEqual(2);
      expect(result.current.messages).toHaveLength(2);
      await waitFor(() => expect(listProposals.mock.calls.length).toBeGreaterThanOrEqual(2));
      await waitFor(() => expect(result.current.proposals).toHaveLength(1));
    });

    it("turns the bubble into a retryable error when the turn fails", async () => {
      const getTurn = vi.fn(async () => ({ turn_id: "t7", status: "failed" as const, error: "se cayó" }));
      const { result } = setup(fakeApi({ listTurns: vi.fn(async () => [pendingTurn]), getTurn }));
      await waitFor(() => expect(result.current.messages.map((m) => m.role)).toEqual(["user", "error"]));
      expect(result.current.messages[1]).toMatchObject({ text: "se cayó", retryText: "hola" });
    });

    it("stops polling after unmount", async () => {
      const getTurn = vi.fn(async () => ({ turn_id: "t7", status: "pending" as const }));
      const { unmount, result } = setup(fakeApi({ listTurns: vi.fn(async () => [pendingTurn]), getTurn }));
      await waitFor(() => expect(getTurn).toHaveBeenCalled());
      unmount();
      const n = getTurn.mock.calls.length;
      await new Promise((r) => setTimeout(r, 60));
      expect(getTurn.mock.calls.length).toBeLessThanOrEqual(n + 1);
      expect(result.current.messages[1]?.text).toBe("El copiloto sigue trabajando…");
    });

    it("does not poll turns that are already done", async () => {
      const getTurn = vi.fn();
      const done = { turn_id: "t9", ts: "2026-03-01T10:00:00Z", user_text: "hola", reply: "buenas", status: "done" as const };
      const { result } = setup(fakeApi({ listTurns: vi.fn(async () => [done]), getTurn }));
      await waitFor(() => expect(result.current.messages).toHaveLength(2));
      await new Promise((r) => setTimeout(r, 30));
      expect(getTurn).not.toHaveBeenCalled();
    });

    it.each([["empty", ""], ["whitespace", "   "], ["literal None", "None"]])(
      "replaces the working bubble with a neutral message when the turn finishes with %s reply",
      async (_n, reply) => {
        const getTurn = vi
          .fn()
          .mockResolvedValueOnce({ turn_id: "t7", status: "pending", still_running: true })
          .mockResolvedValue({ turn_id: "t7", status: "done", reply });
        const { result } = setup(fakeApi({ listTurns: vi.fn(async () => [pendingTurn]), getTurn }));
        await waitFor(() => expect(result.current.messages[1]?.text).toContain("terminó sin respuesta de texto"));
        expect(result.current.messages[1]).toMatchObject({ role: "assistant", turnId: "t7" });
        expect(result.current.messages[1]?.text).toContain("terminó sin respuesta de texto");
        expect(result.current.messages[1]?.text).not.toContain("None");
        expect(result.current.stillRunning).toBe(false);
      },
    );

    it("does not poll a done turn with an empty reply from history", async () => {
      const getTurn = vi.fn();
      const done = { turn_id: "t9", ts: "2026-03-01T10:00:00Z", user_text: "hola", reply: "", status: "done" as const };
      setup(fakeApi({ listTurns: vi.fn(async () => [done]), getTurn }));
      await new Promise((r) => setTimeout(r, 40));
      expect(getTurn).not.toHaveBeenCalled();
    });

    it("keeps the working bubble through one 500 and then shows the reply with no error", async () => {
      const getTurn = vi
        .fn()
        .mockRejectedValueOnce(new ApiError(500, "boom"))
        .mockResolvedValue({ turn_id: "t7", status: "done", reply: "Listo" });
      const { result } = setup(fakeApi({ listTurns: vi.fn(async () => [pendingTurn]), getTurn }));
      await waitFor(() => expect(result.current.messages[1]?.text).toBe("Listo"));
      expect(result.current.messages.map((m) => m.role)).toEqual(["user", "assistant"]);
      expect(getTurn).toHaveBeenCalledTimes(2);
    });

    it("retries network errors (status 0) too", async () => {
      const getTurn = vi
        .fn()
        .mockRejectedValueOnce(new ApiError(0, "sin red"))
        .mockResolvedValue({ turn_id: "t7", status: "done", reply: "Listo" });
      const { result } = setup(fakeApi({ listTurns: vi.fn(async () => [pendingTurn]), getTurn }));
      await waitFor(() => expect(result.current.messages[1]?.text).toBe("Listo"));
    });

    it("resets the error counter after a successful poll", async () => {
      const e = () => new ApiError(500, "boom");
      const pend = { turn_id: "t7", status: "pending" as const };
      const getTurn = vi
        .fn()
        .mockRejectedValueOnce(e()).mockRejectedValueOnce(e()).mockRejectedValueOnce(e()).mockRejectedValueOnce(e())
        .mockResolvedValueOnce(pend)
        .mockRejectedValueOnce(e()).mockRejectedValueOnce(e()).mockRejectedValueOnce(e()).mockRejectedValueOnce(e())
        .mockResolvedValue({ turn_id: "t7", status: "done", reply: "Listo" });
      const { result } = setup(fakeApi({ listTurns: vi.fn(async () => [pendingTurn]), getTurn }));
      await waitFor(() => expect(result.current.messages[1]?.text).toBe("Listo"));
    });

    it("shows a non-retry error once repeated 500s exhaust the budget, keeping the bubble until then", async () => {
      const getTurn = vi.fn().mockRejectedValue(new ApiError(500, "boom"));
      const { result } = setup(fakeApi({ listTurns: vi.fn(async () => [pendingTurn]), getTurn }));
      await waitFor(() => expect(result.current.messages[1]?.text).toBe("El copiloto sigue trabajando…"));
      await waitFor(() => expect(result.current.messages[1]?.role).toBe("error"));
      expect(result.current.messages[1]?.text).toBe("No pude confirmar el estado; vuelve a cargar");
      expect(result.current.messages[1]?.retryText).toBeUndefined();
      expect(getTurn).toHaveBeenCalledTimes(5);
    });

    it("fails immediately, with retry, on a non-404 4xx", async () => {
      const getTurn = vi.fn().mockRejectedValue(new ApiError(400, "malo"));
      const { result } = setup(fakeApi({ listTurns: vi.fn(async () => [pendingTurn]), getTurn }));
      await waitFor(() => expect(result.current.messages[1]?.role).toBe("error"));
      expect(result.current.messages[1]).toMatchObject({ text: "malo", retryText: "hola" });
      expect(getTurn).toHaveBeenCalledTimes(1);
    });
  });

  describe("live turn polling errors", () => {
    it("survives one 500 and shows the reply", async () => {
      const getTurn = vi
        .fn()
        .mockRejectedValueOnce(new ApiError(500, "boom"))
        .mockResolvedValue({ turn_id: "t1", status: "done", reply: "Pide 40" });
      const { result } = setup(fakeApi({ getTurn }));
      await act(async () => { await result.current.send("hola"); });
      expect(result.current.messages.map((m) => m.role)).toEqual(["user", "assistant"]);
    });

    it("shows a non-retry error when repeated 500s exhaust the budget", async () => {
      const getTurn = vi.fn().mockRejectedValue(new ApiError(500, "boom"));
      const { result } = setup(fakeApi({ getTurn }));
      await act(async () => { await result.current.send("hola"); });
      expect(result.current.messages.at(-1)).toMatchObject({ role: "error", text: "No pude confirmar el estado; vuelve a cargar" });
      expect(result.current.messages.at(-1)?.retryText).toBeUndefined();
      expect(result.current.status).toBe("idle");
    });

    it("fails immediately on a 400", async () => {
      const getTurn = vi.fn().mockRejectedValue(new ApiError(400, "malo"));
      const { result } = setup(fakeApi({ getTurn }));
      await act(async () => { await result.current.send("hola"); });
      expect(result.current.messages.at(-1)).toMatchObject({ role: "error", text: "malo", retryText: "hola" });
      expect(getTurn).toHaveBeenCalledTimes(1);
    });
  });

  it("tolerates a 404 right after the POST, then shows the reply", async () => {
    const getTurn = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(404, "not found"))
      .mockRejectedValueOnce(new ApiError(404, "not found"))
      .mockResolvedValue({ turn_id: "t1", status: "done", reply: "<think>x</think>Pide 40" });
    const api = fakeApi({ getTurn });
    const { result } = setup(api);
    await act(async () => { await result.current.send("¿Qué pido?"); });
    await waitFor(() => expect(result.current.messages.at(-1)?.text).toBe("Pide 40"));
    expect(result.current.messages.at(-1)).toMatchObject({ role: "assistant", turnId: "t1" });
    expect(result.current.messages[0]).toMatchObject({ role: "user", text: "¿Qué pido?" });
    expect(result.current.status).toBe("idle");
    expect(getTurn).toHaveBeenCalledTimes(3);
  });

  it("gives up after the 404 grace window", async () => {
    const api = fakeApi({ getTurn: vi.fn().mockRejectedValue(new ApiError(404, "nf")) });
    const { result } = setup(api, { ...OPTS, notFoundGraceMs: 20 });
    await act(async () => { await result.current.send("hola"); });
    await waitFor(() => expect(result.current.messages.at(-1)?.role).toBe("error"));
  });

  it("flags still_running while pending", async () => {
    const getTurn = vi
      .fn()
      .mockResolvedValueOnce({ turn_id: "t1", status: "pending", still_running: true })
      .mockImplementation(async () => {
        await new Promise((r) => setTimeout(r, 200));
        return { turn_id: "t1", status: "done", reply: "listo" };
      });
    const { result } = setup(fakeApi({ getTurn }));
    act(() => { void result.current.send("hola"); });
    await waitFor(() => expect(result.current.stillRunning).toBe(true));
    await waitFor(() => expect(result.current.messages.at(-1)?.text).toBe("listo"));
    expect(result.current.stillRunning).toBe(false);
  });

  it("shows an error bubble on failed and retries without duplicating the question", async () => {
    const getTurn = vi
      .fn()
      .mockResolvedValueOnce({ turn_id: "t1", status: "failed", error: "boom" })
      .mockResolvedValue({ turn_id: "t2", status: "done", reply: "ahora sí" });
    const sendMessage = vi.fn().mockResolvedValueOnce({ turn_id: "t1" }).mockResolvedValueOnce({ turn_id: "t2" });
    const { result } = setup(fakeApi({ getTurn, sendMessage }));
    await act(async () => { await result.current.send("hola"); });
    await waitFor(() => expect(result.current.messages.at(-1)).toMatchObject({ role: "error", text: "boom" }));
    await act(async () => { await result.current.retry(); });
    await waitFor(() => expect(result.current.messages.at(-1)?.text).toBe("ahora sí"));
    expect(result.current.messages.filter((m) => m.role === "user")).toHaveLength(1);
    expect(result.current.messages.some((m) => m.role === "error")).toBe(false);
    expect(sendMessage).toHaveBeenLastCalledWith("c1", "hola");
  });

  it("shows an error bubble when the POST fails", async () => {
    const { result } = setup(fakeApi({ sendMessage: vi.fn().mockRejectedValue(new ApiError(500, "caído")) }));
    await act(async () => { await result.current.send("hola"); });
    expect(result.current.messages.at(-1)).toMatchObject({ role: "error" });
  });

  // Stateful proposals backend: deciding removes the proposal from the pending list.
  const proposalsApi = (over: Record<string, unknown> = {}) => {
    let list = [proposalA, { ...proposalA, proposal_id: "p2", status: "approved" }];
    const listProposals = vi.fn(async () => list);
    const decide = vi.fn(async (id: string) => { list = list.filter((p) => p.proposal_id !== id); return {}; });
    return { listProposals, decide, api: fakeApi({ listProposals, decide, ...over }) };
  };

  it("loads pending proposals on chat load", async () => {
    const { api, listProposals } = proposalsApi();
    const { result } = setup(api);
    await waitFor(() => expect(result.current.proposals.map((p) => p.proposal_id)).toEqual(["p1"]));
    expect(listProposals).toHaveBeenCalledWith({ case_id: "c1", status: "pending" });
  });

  it("refreshes proposals after a turn reaches done", async () => {
    let list: unknown[] = [];
    const listProposals = vi.fn(async () => list);
    const getTurn = vi.fn(async () => { list = [proposalA]; return { turn_id: "t1", status: "done", reply: "Te propuse un pedido" }; });
    const { result } = setup(fakeApi({ listProposals, getTurn }));
    await waitFor(() => expect(listProposals).toHaveBeenCalledTimes(1));
    expect(result.current.proposals).toEqual([]);
    await act(async () => { await result.current.send("pide"); });
    await waitFor(() => expect(result.current.proposals).toHaveLength(1));
    expect(result.current.status).toBe("idle");
  });

  it("loads proposals on waiting_approval and decides with an Idempotency-Key", async () => {
    const { api, decide } = proposalsApi({ getTurn: vi.fn(async () => ({ turn_id: "t1", status: "waiting_approval" })) });
    const { result } = setup(api);
    await act(async () => { await result.current.send("pide"); });
    await waitFor(() => expect(result.current.status).toBe("waiting_approval"));
    await waitFor(() => expect(result.current.proposals.map((p) => p.proposal_id)).toEqual(["p1"]));
    await act(async () => { await result.current.decide("p1", true); });
    expect(decide).toHaveBeenCalledWith("p1", { approved: true }, { idempotencyKey: expect.stringMatching(/^[0-9a-f-]{36}$/) });
    await waitFor(() => expect(result.current.proposals).toEqual([]));
  });

  it("sends the reason on reject and a fresh key per click", async () => {
    const decide = vi.fn(async () => ({}));
    const { result } = setup(fakeApi({ decide }));
    await waitFor(() => expect(result.current.proposals).toHaveLength(1));
    await act(async () => { await result.current.decide("p1", false, "caro"); });
    await act(async () => { await result.current.decide("p1", false, "caro"); });
    expect((decide.mock.calls[0] as unknown[])[1]).toEqual({ approved: false, reason: "caro" });
    const keys = decide.mock.calls.map((c) => (c as unknown as [string, unknown, { idempotencyKey: string }])[2].idempotencyKey);
    expect(keys[0]).not.toBe(keys[1]);
  });

  it("treats a 409 as already decided: refreshes without an error", async () => {
    const decide = vi.fn().mockRejectedValue(new ApiError(409, "ya decidida"));
    const listProposals = vi.fn().mockResolvedValueOnce([proposalA]).mockResolvedValue([]);
    const { result } = setup(fakeApi({ listProposals, decide }));
    await waitFor(() => expect(result.current.proposals).toHaveLength(1));
    await act(async () => { await result.current.decide("p1", true); });
    await waitFor(() => expect(result.current.proposals).toEqual([]));
    expect(result.current.decisionError).toBeNull();
    expect(listProposals).toHaveBeenCalledTimes(2);
  });

  it("keeps reply_meta on the assistant message", async () => {
    const meta = { source: "fast", template: "reorder", elapsed_ms: 1200 };
    const { result } = setup(fakeApi({ getTurn: vi.fn(async () => ({ turn_id: "t1", status: "done", reply: "ok", reply_meta: meta })) }));
    await act(async () => { await result.current.send("hola"); });
    await waitFor(() => expect(result.current.messages.at(-1)?.meta).toEqual(meta));
  });
});

describe("useChat send with display text", () => {
  it("shows the short text in the bubble but sends the full text with its context", async () => {
    const api = fakeApi();
    const { result } = setup(api);
    await act(async () => { await result.current.send("Contexto: X (i1).\nAnaliza: X", { display: "Analiza: X" }); });
    expect(api.sendMessage).toHaveBeenCalledWith("c1", "Contexto: X (i1).\nAnaliza: X");
    expect(result.current.messages.find((m) => m.role === "user")).toMatchObject({ text: "Analiza: X" });
    expect(result.current.messages.find((m) => m.role === "user")?.ts).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });
});

describe("useChat message context", () => {
  const ctx = { issue_id: "S030|stockout_risk|SKU-1", option_id: "o1", mode: "analizar" as const };

  it("sends the context as a field of POST /messages and keeps the text clean", async () => {
    const api = fakeApi();
    const { result } = setup(api);
    await act(async () => { await result.current.send("Analiza: Pedir pavo", { context: ctx }); });
    expect(api.sendMessage).toHaveBeenCalledWith("c1", "Analiza: Pedir pavo", ctx);
  });

  it("sends no third argument when there is no context", async () => {
    const api = fakeApi();
    const { result } = setup(api);
    await act(async () => { await result.current.send("hola"); });
    expect(api.sendMessage).toHaveBeenCalledWith("c1", "hola");
  });

  it("passes voice: true to the API for push-to-talk sends", async () => {
    const api = fakeApi();
    const { result } = setup(api);
    await act(async () => { await result.current.send("hola", { voice: true }); });
    expect(api.sendMessage).toHaveBeenCalledWith("c1", "hola", undefined, { voice: true });
  });

  it("resends the same context when the user retries", async () => {
    const api = fakeApi({ getTurn: vi.fn(async () => ({ turn_id: "t1", status: "failed", error: "se cayó" })) });
    const { result } = setup(api);
    await act(async () => { await result.current.send("Analiza", { context: ctx, display: "Analiza: X" }); });
    await act(async () => { await result.current.retry(); });
    expect(vi.mocked(api.sendMessage).mock.calls.map((c) => c[2])).toEqual([ctx, ctx]);
  });
});

describe("useChat turn progress", () => {
  const consulting = [{ agent_id: "supply", display_name_es: "Analista de abastecimiento", state: "consulting" as const }, { agent_id: "past", display_name_es: "Analista histórico", state: "done" as const }];

  it("exposes the agents being consulted while the turn is pending and clears them when it is done", async () => {
    let finished = false;
    const getTurn = vi.fn(async () => (finished ? { turn_id: "t1", status: "done" as const, reply: "listo", progress: [] } : { turn_id: "t1", status: "pending" as const, progress: consulting }));
    const { result } = setup(fakeApi({ getTurn }));
    await act(async () => { void result.current.send("hola"); });
    await waitFor(() => expect(result.current.progress).toEqual(consulting));
    finished = true;
    await waitFor(() => expect(result.current.status).toBe("idle"));
    expect(result.current.progress).toEqual([]);
  });

  it("has no progress when the backend does not send it", async () => {
    const { result } = setup(fakeApi());
    await act(async () => { await result.current.send("hola"); });
    expect(result.current.progress).toEqual([]);
  });
});

describe("useChat partial reply", () => {
  it("shows the partial reply while the turn runs and the final reply replaces it", async () => {
    let finished = false;
    const getTurn = vi.fn(async () =>
      finished
        ? { turn_id: "t1", status: "done" as const, reply: "Hoy vendiste 12 cajas y 3 bolsas." }
        : { turn_id: "t1", status: "pending" as const, partial_reply: "<think>x</think>Hoy vendiste 12" },
    );
    const { result } = setup(fakeApi({ getTurn }));
    await act(async () => { void result.current.send("¿cómo vamos?"); });
    await waitFor(() => expect(result.current.partialReply).toBe("Hoy vendiste 12"));
    expect(result.current.messages.filter((m) => m.role === "assistant")).toEqual([]);
    finished = true;
    await waitFor(() => expect(result.current.status).toBe("idle"));
    expect(result.current.partialReply).toBe("");
    expect(result.current.messages.filter((m) => m.role === "assistant").map((m) => m.text)).toEqual(["Hoy vendiste 12 cajas y 3 bolsas."]);
  });

  it("keeps the last partial while a later read carries none, and clears it when the turn fails", async () => {
    const getTurn = vi
      .fn()
      .mockResolvedValueOnce({ turn_id: "t1", status: "pending", partial_reply: "Revisando" })
      .mockResolvedValueOnce({ turn_id: "t1", status: "pending" })
      .mockImplementation(async () => {
        await new Promise((r) => setTimeout(r, 50));
        return { turn_id: "t1", status: "failed", error: "boom" };
      });
    const { result } = setup(fakeApi({ getTurn }));
    act(() => { void result.current.send("hola"); });
    await waitFor(() => expect(result.current.partialReply).toBe("Revisando"));
    await waitFor(() => expect(getTurn).toHaveBeenCalledTimes(3));
    expect(result.current.partialReply).toBe("Revisando");
    await waitFor(() => expect(result.current.messages.at(-1)?.role).toBe("error"));
    expect(result.current.partialReply).toBe("");
  });

  it("has no partial reply when the backend does not send one", async () => {
    const { result } = setup(fakeApi());
    await act(async () => { await result.current.send("hola"); });
    expect(result.current.partialReply).toBe("");
  });

  it("shows a resumed turn's partial reply in its pending bubble until the final one", async () => {
    let finished = false;
    const listTurns = vi.fn().mockResolvedValue([
      { turn_id: "t9", ts: "2026-10-14T10:00:00Z", user_text: "¿qué pido?", status: "pending", reply: null },
    ]);
    const getTurn = vi.fn(async () =>
      finished
        ? { turn_id: "t9", status: "done" as const, reply: "Pide 40 cajas." }
        : { turn_id: "t9", status: "pending" as const, partial_reply: "Pide 40" },
    );
    const { result } = setup(fakeApi({ listTurns, getTurn }));
    await waitFor(() => expect(result.current.messages.at(-1)?.text).toBe("Pide 40"));
    finished = true;
    await waitFor(() => expect(result.current.messages.at(-1)?.text).toBe("Pide 40 cajas."));
  });
});
