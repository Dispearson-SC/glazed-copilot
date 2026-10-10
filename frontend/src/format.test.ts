import { money, usd } from "./format";

describe("usd", () => {
  it("groups thousands like the design ($4,850.00)", () => {
    expect(usd(4850)).toBe("$4,850.00");
    expect(usd(1135.18)).toBe("$1,135.18");
    expect(usd(1234567.8)).toBe("$1,234,567.80");
  });

  it("keeps small and negative amounts", () => {
    expect(usd(9.79)).toBe("$9.79");
    expect(usd(-1500)).toBe("-$1,500.00");
  });

  it("money falls back for missing values", () => {
    expect(money(null)).not.toMatch(/\$/);
  });
});
