import { describe, expect, it } from "vitest";
import { bestOption, deadlineUrgency, isLowConfidence, rangeText, tierInfo, wasteMid } from "./issues";
import { optDoNothing, optN0, optN2, optN3 } from "./test/fixtures";

describe("bestOption", () => {
  it("picks the highest net_usd_mid among options with tier != N0", () => {
    expect(bestOption([optDoNothing, optN0, optN2, optN3])?.option_id).toBe("o-n3");
  });
  it("ignores N0 options even when they have the highest net", () => {
    expect(bestOption([optDoNothing, optN0, optN2])?.option_id).toBe("o-n2");
  });
  it("returns do_nothing when it wins", () => {
    const winner = { ...optDoNothing, net_usd_mid: 999 };
    expect(bestOption([winner, optN2])?.option_id).toBe("o-nothing");
  });
  it("returns null for an empty list", () => {
    expect(bestOption([])).toBeNull();
  });
});

describe("tierInfo", () => {
  it.each([
    ["N0", "N0 no actuar"],
    ["N1", "N1 automático"],
    ["N2", "N2 propuesta"],
    ["N3", "N3 diálogo"],
  ] as const)("maps %s to %s", (tier, label) => {
    expect(tierInfo(tier).label).toBe(label);
  });
});

describe("deadlineUrgency", () => {
  it("flags today, tomorrow and overdue relative to the simulated date", () => {
    expect(deadlineUrgency("2026-03-01", "2026-03-01")).toBe("today");
    expect(deadlineUrgency("2026-03-02", "2026-03-01")).toBe("tomorrow");
    expect(deadlineUrgency("2026-02-28", "2026-03-01")).toBe("overdue");
    expect(deadlineUrgency("2026-03-05", "2026-03-01")).toBeNull();
    expect(deadlineUrgency(null, "2026-03-01")).toBeNull();
  });
  it("handles month boundaries", () => {
    expect(deadlineUrgency("2026-03-01", "2026-02-28")).toBe("tomorrow");
  });
});

describe("misc helpers", () => {
  it("low confidence below 0.5", () => {
    expect(isLowConfidence(0.49)).toBe(true);
    expect(isLowConfidence(0.5)).toBe(false);
  });
  it("renders ranges", () => {
    expect(rangeText({ low: 10, mid: 20, high: 30 })).toBe("$10.00 – $30.00");
  });
  it("accepts a plain number or a range for waste", () => {
    expect(wasteMid(12)).toBe(12);
    expect(wasteMid({ low: 1, mid: 2, high: 3 })).toBe(2);
  });
});

import { actionLabel, alertTypeLabel, kindLabel, severityCell } from "./issues";

describe("wave 6 labels", () => {
  it("names the new alert types and kinds", () => {
    expect(alertTypeLabel(21)).toBe("Cumplimiento (Centinela)");
    expect(alertTypeLabel(5)).toBe("Pedido");
    expect(alertTypeLabel(7)).toBe("Promoción");
    expect(alertTypeLabel(19)).toBe("Calendario");
    expect(alertTypeLabel(9)).toBe("Integridad de datos");
    expect(kindLabel("compliance_deviation")).toBe("Desviación de cumplimiento");
    expect(kindLabel("inflated_order")).toBe("Pedido inflado");
    expect(kindLabel("misleading_promo")).toBe("Auditoría de promoción");
    expect(kindLabel("calendar_uplift")).toBe("Alza por calendario");
    expect(kindLabel("sku_key_mismatch")).toBe("SKU con llave inconsistente");
    expect(kindLabel("orphan_sku")).toBe("SKU huérfano");
    expect(kindLabel("mystery")).toBe("mystery");
    expect(actionLabel("data_fix_task")).toBe("Tarea de corrección de datos");
    expect(actionLabel("place_order")).toBe("place_order");
  });

  it("shows exposure instead of severity for integrity issues", () => {
    expect(severityCell({ severity_usd: 5, issue: { category: "integrity", exposure_usd: 1234.5 } })).toBe("Exposición $1234.50");
    expect(severityCell({ severity_usd: 58.92, issue: { kind: "orphan_sku", exposure_usd: 10 } })).toBe("Exposición $10.00");
    expect(severityCell({ severity_usd: 12.3, issue: {} })).toBe("12.30");
  });
});
