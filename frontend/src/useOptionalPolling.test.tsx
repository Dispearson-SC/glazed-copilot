import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { useOptionalPolling } from "./useOptionalPolling";

describe("useOptionalPolling", () => {
  it("returns data when the route answers", async () => {
    const { result } = renderHook(() => useOptionalPolling(async () => ({ a: 1 }), 60_000, true, []));
    await waitFor(() => expect(result.current.data).toEqual({ a: 1 }));
    expect(result.current.soon).toBe(false);
  });
  it("flags 404 and 501 as soon, with no error", async () => {
    for (const status of [404, 501]) {
      const { result } = renderHook(() => useOptionalPolling(async () => { throw new ApiError(status, "nf"); }, 60_000, true, []));
      await waitFor(() => expect(result.current.soon).toBe(true));
      expect(result.current.error).toBeNull();
      expect(result.current.data).toBeNull();
    }
  });
  it("keeps real errors as errors", async () => {
    const { result } = renderHook(() => useOptionalPolling(async () => { throw new ApiError(500, "boom"); }, 60_000, true, []));
    await waitFor(() => expect(result.current.error?.message).toBe("boom"));
    expect(result.current.soon).toBe(false);
  });
});
