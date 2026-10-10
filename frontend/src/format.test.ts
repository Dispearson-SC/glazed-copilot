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

import { dateLabel } from "./format";
describe("dateLabel", () => {
  it("is 'Sábado 10 de octubre' like the copilot design: weekday, day and month, no comma or year", () => {
    expect(dateLabel("2026-10-10")).toBe("Sábado 10 de octubre");
    expect(dateLabel("2026-07-19")).toBe("Domingo 19 de julio");
  });
});

describe("signedUsd", () => {
  it("signs gains, losses and leaves zero bare", async () => {
    const { signedUsd } = await import("./format");
    expect(signedUsd(1234.5)).toBe("+$1,234.50");
    expect(signedUsd(-22)).toBe("-$22.00");
    expect(signedUsd(0)).toBe("$0.00");
  });
});
