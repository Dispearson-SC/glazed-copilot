import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePolling } from "./usePolling";

describe("usePolling", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("loads immediately then at each interval", async () => {
    const fn = vi.fn(async () => 1);
    renderHook(() => usePolling(fn, 1000));
    await act(async () => {});
    expect(fn).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it("stops polling once enabled becomes false", async () => {
    const fn = vi.fn(async () => 1);
    const { rerender } = renderHook(({ on }) => usePolling(fn, 1000, on), { initialProps: { on: true } });
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    const calls = fn.mock.calls.length;
    rerender({ on: false });
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(fn.mock.calls.length).toBe(calls);
  });

  it("exposes data and error states", async () => {
    const fn = vi.fn().mockRejectedValueOnce(new Error("down")).mockResolvedValue("ok");
    const { result } = renderHook(() => usePolling(fn, 1000));
    await act(async () => {});
    expect(result.current.error?.message).toBe("down");
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(result.current.data).toBe("ok");
    expect(result.current.error).toBeNull();
  });
});

describe("usePolling deps", () => {
  it("reloads immediately when deps change", async () => {
    const fn = vi.fn(async () => 1);
    const { rerender } = renderHook(({ k }) => usePolling(fn, 1000, true, [k]), { initialProps: { k: "a" } });
    await act(async () => {});
    rerender({ k: "b" });
    await act(async () => {});
    expect(fn).toHaveBeenCalledTimes(2);
  });
});
