import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { ApiProvider } from "./ApiContext";
import { ApiError } from "./api";
import { buildPendingItems } from "./data/copilot";
import { CopilotProvider } from "./state/copilotStore";
import { pendingA } from "./test/copilotFixtures";
import { fakeApi } from "./test/helpers";
import { useDecide } from "./useDecide";

const [tech, approval] = buildPendingItems(pendingA, "2026-07-19");

function setup(over: Record<string, unknown> = {}) {
  const api = fakeApi(over);
  const refresh = vi.fn(async () => {});
  const wrapper = ({ children }: { children: ReactNode }) => (
    <ApiProvider api={api}>
      <CopilotProvider>{children}</CopilotProvider>
    </ApiProvider>
  );
  const hook = renderHook(() => useDecide("c1", refresh), { wrapper });
  return { api, refresh, hook };
}
const keyOf = (api: ReturnType<typeof fakeApi>, call: number) => (vi.mocked(api.recordDecision).mock.calls[call] as unknown as [string, unknown, { idempotencyKey: string }])[2].idempotencyKey;

describe("useDecide busy state", () => {
  it("exposes the id of the card with a request in flight and clears it afterwards", async () => {
    let release: (v: unknown) => void = () => {};
    const { hook } = setup({ recordDecision: vi.fn(() => new Promise((r) => { release = r; })) });
    expect(hook.result.current.busyId).toBeNull();
    let p!: Promise<boolean>;
    act(() => { p = hook.result.current.decide(tech, true); });
    await waitFor(() => expect(hook.result.current.busyId).toBe(tech.id));
    await act(async () => { release({ decision_id: "d", proposal_id: "d", status: "approved" }); await p; });
    expect(hook.result.current.busyId).toBeNull();
  });
});

describe("useDecide idempotency", () => {
  it("reuses ONE Idempotency-Key when the same decision is retried after a transient failure", async () => {
    const recordDecision = vi.fn().mockRejectedValueOnce(new ApiError(503, "down")).mockResolvedValue({ decision_id: "d", proposal_id: "d", status: "approved" });
    const { api, hook } = setup({ recordDecision });
    await act(async () => { await hook.result.current.decide(tech, true); });
    await act(async () => { await hook.result.current.decide(tech, true); });
    expect(recordDecision).toHaveBeenCalledTimes(2);
    expect(keyOf(api, 0)).toBe(keyOf(api, 1));
  });

  it("sends a double tap once: the second tap joins the request in flight", async () => {
    let release: (v: unknown) => void = () => {};
    const recordDecision = vi.fn(() => new Promise((r) => { release = r; }));
    const { hook } = setup({ recordDecision });
    let first!: Promise<boolean>;
    let second!: Promise<boolean>;
    act(() => {
      first = hook.result.current.decide(tech, true);
      second = hook.result.current.decide(tech, true);
    });
    expect(recordDecision).toHaveBeenCalledTimes(1);
    await act(async () => { release({ decision_id: "d", proposal_id: "d", status: "approved" }); await Promise.all([first, second]); });
  });

  it("uses a different key per card and per action, and a fresh one after a definitive outcome", async () => {
    const recordDecision = vi.fn(async () => ({ decision_id: "d", proposal_id: "d", status: "approved" }));
    const { api, hook } = setup({ recordDecision });
    await act(async () => { await hook.result.current.decide(tech, true); });
    await act(async () => { await hook.result.current.decide(approval, true); });
    await act(async () => { await hook.result.current.decide(tech, true); });
    await act(async () => { await hook.result.current.decide(tech, false, { label: "Otro", text: "x" }); });
    const keys = [0, 1, 2, 3].map((i) => keyOf(api, i));
    expect(new Set(keys).size).toBe(4);
  });

  it("keeps the key after a network error (status 0) and drops it after a definitive 400", async () => {
    const recordDecision = vi.fn().mockRejectedValueOnce(new ApiError(0, "net")).mockRejectedValueOnce(new ApiError(400, "bad")).mockResolvedValue({ decision_id: "d", proposal_id: "d", status: "approved" });
    const { api, hook } = setup({ recordDecision });
    await act(async () => { await hook.result.current.decide(tech, true); });
    await act(async () => { await hook.result.current.decide(tech, true); }); // retry: same key, definitive 400
    await act(async () => { await hook.result.current.decide(tech, true); }); // new intent: new key
    expect(keyOf(api, 0)).toBe(keyOf(api, 1));
    expect(keyOf(api, 2)).not.toBe(keyOf(api, 1));
  });
});

describe("useDecide reject hardening", () => {
  it("never sends a rejection without a reason", async () => {
    const { api, hook } = setup();
    await act(async () => { expect(await hook.result.current.decide(tech, false)).toBe(false); });
    await act(async () => { expect(await hook.result.current.decide(tech, false, { label: "", text: "" })).toBe(false); });
    expect(api.recordDecision).not.toHaveBeenCalled();
  });

  it("keeps approve and reject intents separate: a reject never joins an approve in flight", async () => {
    const releases: Array<(v: unknown) => void> = [];
    const recordDecision = vi.fn(() => new Promise((r) => { releases.push(r); }));
    const { hook } = setup({ recordDecision });
    let a!: Promise<boolean>;
    let r!: Promise<boolean>;
    act(() => { a = hook.result.current.decide(tech, true); });
    act(() => { r = hook.result.current.decide(tech, false, { label: "Otro", text: "" }); });
    expect(recordDecision).toHaveBeenCalledTimes(2);
    const bodies = recordDecision.mock.calls.map((c) => (c as unknown as [string, { approved: boolean }])[1].approved);
    expect(bodies).toEqual([true, false]);
    releases.forEach((rel) => rel({ decision_id: "d", proposal_id: "d", status: "x" }));
    await act(async () => { await Promise.all([a, r]); });
  });
});

describe("useDecide choosing an alternative", () => {
  it("posts the chosen option_id, toasts its label and keeps a separate intent from the recommendation", async () => {
    const recordDecision = vi.fn().mockResolvedValue({ decision_id: "d", proposal_id: "d", status: "approved" });
    const { api, hook } = setup({ recordDecision });
    await act(async () => { await hook.result.current.decide(approval, true, undefined, { optionId: "alt-1", label: "No hacer nada" }); });
    const body = vi.mocked(api.recordDecision).mock.calls[0][1] as { option_id: string; approved: boolean };
    expect(body).toMatchObject({ issue_id: approval.issueId, option_id: "alt-1", approved: true });
    expect(body.option_id).not.toBe(approval.optionId);
    await act(async () => { await hook.result.current.decide(approval, true); });
    expect(keyOf(api, 0)).not.toBe(keyOf(api, 1));
  });
});
