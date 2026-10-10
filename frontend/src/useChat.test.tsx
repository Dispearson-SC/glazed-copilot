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
