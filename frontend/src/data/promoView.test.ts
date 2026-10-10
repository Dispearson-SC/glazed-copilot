import { describe, expect, it } from "vitest";
import { promoView } from "./copilot";

const base = { action_type: "activate_promo", params: { discount_pct: 20, days: 3, start_date: "2026-07-20", end_date: "2026-07-22" } };

describe("promoView fallbacks", () => {
  it("returns null for other actions or without discount/days", () => {
    expect(promoView({ action_type: "skip_order", params: {} })).toBeNull();
    expect(promoView({ action_type: "activate_promo", params: { days: 3 } })).toBeNull();
    expect(promoView({ action_type: "activate_promo", params: { discount_pct: 20, days: Number.NaN } })).toBeNull();
  });

  it("drops the date range instead of throwing on malformed dates", () => {
    for (const bad of [123, "mañana", null, { d: 1 }]) {
      expect(() => promoView({ ...base, params: { ...base.params, start_date: bad as never } })).not.toThrow();
      expect(JSON.stringify(promoView({ ...base, params: { ...base.params, start_date: bad as never } }))).not.toContain("(");
    }
  });

  it("keeps the date range for valid ISO dates", () => {
    expect(JSON.stringify(promoView(base))).toMatch(/\(.+–.+\)/);
  });
});
