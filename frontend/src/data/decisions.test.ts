import { describe, expect, it, vi } from "vitest";
import { ApiError, type Api } from "../api";
import { analysisApproval, pendingA } from "../test/copilotFixtures";
import { analysisSections, buildPendingItems, deadlineText, fetchIssueAnalysis, tierLabel } from "./copilot";

const SIM = "2026-07-19";

describe("buildPendingItems", () => {
  it("returns nothing without data", () => {
    expect(buildPendingItems(null, SIM)).toEqual([]);
  });

  it("keeps the backend split: technical first, approvals after, nothing re-derived", () => {
    expect(buildPendingItems(pendingA, SIM).map((i) => [i.id, i.kind])).toEqual([
      ["S030|stockout_risk|SKU-100263", "tech"],
      ["S030|overstock_waste|SKU-100502", "approval"],
    ]);
  });

  it("builds the technical card from the pending item (backend Spanish text and chips)", () => {
    const t = buildPendingItems(pendingA, SIM)[0];
    expect(t).toMatchObject({
      optionId: "8f63a675ef2b", tier: "N2", level: "N2 · Propuesta", title: "Pedir 10 unidades de Md Choc Stout C.B. Wsweet Cold Foam",
      supplier: "Summit Frozen Foods", arrive: "llega mar 21", cost: "$14.60", deadline: "Hoy", confPct: "41%", icon: "shopping_basket", readOnly: false,
    });
    expect(t.chips).toEqual(["Venta perdida esperada $10.63", "Merma esperada $0.96", "Riesgo de desabasto sin pedido 100%"]);
    expect(t.warn).toContain("mínimo del proveedor");
    expect(t.why).toContain("se agotaría el 2026-07-21");
  });

  it("builds the approval card from the recommendation", () => {
    const a = buildPendingItems(pendingA, SIM)[1];
    expect(a).toMatchObject({ title: "Omitir el pedido de 12 Croiss-Ant Donuts en este ciclo", level: "N2 · Propuesta", value: "+$58.92", confPct: "74%", deadline: "Hoy", optionId: "65ead6dcd46e" });
    expect(a.summary).toContain("merma de los últimos 14 días");
  });

  it("shows a null deadline and a null confidence honestly", () => {
    const p = { ...pendingA, technical: [{ ...pendingA.technical[0], deadline: null, confidence: null }] };
    expect(buildPendingItems(p, SIM)[0]).toMatchObject({ deadline: "Sin fecha límite", confPct: "Sin datos" });
  });

  it("marks a technical line without issue or option as read-only", () => {
    const p = { ...pendingA, technical: [{ ...pendingA.technical[0], issue_id: null, option_id: null }] };
    expect(buildPendingItems(p, SIM)[0]).toMatchObject({ id: "line|SKU-100263", readOnly: true, optionId: "", issueId: "" });
  });
});

describe("analysisSections", () => {
  it("builds the analysis sections from the backend analysis", () => {
    const s = analysisSections("analizar", analysisApproval);
    expect(s.map((x) => x.label)).toEqual(["Problema", "Recomendación", "Pros", "Contras", "Requiere tu aprobación"]);
    expect(s.find((x) => x.label === "Contras")!.items).toEqual(["Omitir el pedido puede causar un desabasto antes de la próxima entrega."]);
  });

  it("builds the dialogue sections and lists alternatives", () => {
    const s = analysisSections("dialogo", analysisApproval);
    expect(s.map((x) => x.label)).toEqual(["Por qué", "Si aceptas", "Si no actúas", "Alternativas"]);
    expect(s[3].items).toEqual(["No hacer nada (efecto neto $0.00)"]);
  });

  it("omits the approval section when no approval is required and says 'Sin datos' for empty lists", () => {
    const s = analysisSections("analizar", { ...analysisApproval, requires_approval: false, pros: [] });
    expect(s.map((x) => x.label)).not.toContain("Requiere tu aprobación");
    expect(s.find((x) => x.label === "Pros")!.items).toEqual(["Sin datos"]);
  });
});

describe("fetchIssueAnalysis", () => {
  const apiWith = (fn: () => Promise<unknown>) => ({ getAnalysis: vi.fn(fn) }) as unknown as Api;
  it("passes a 200 through, maps 404 to 'soon' and other failures to an error", async () => {
    expect(await fetchIssueAnalysis(apiWith(async () => analysisApproval), "c1", "i")).toEqual({ status: "ok", data: analysisApproval });
    expect(await fetchIssueAnalysis(apiWith(async () => { throw new ApiError(404, "x"); }), "c1", "i")).toEqual({ status: "soon" });
    expect(await fetchIssueAnalysis(apiWith(async () => { throw new ApiError(500, "boom"); }), "c1", "i")).toEqual({ status: "error", message: "boom" });
  });
});

describe("labels", () => {
  it("names tiers and deadlines", () => {
    expect(tierLabel("N3")).toBe("N3 · Diálogo");
    expect(tierLabel("N1")).toBe("N1 · Automática");
    expect(deadlineText("2026-07-19", SIM)).toBe("Hoy");
    expect(deadlineText("2026-07-21", SIM)).toBe("Antes del mar 21");
    expect(deadlineText("2026-07-17", SIM)).toBe("Venció vie 17");
    expect(deadlineText(null, SIM)).toBe("Sin fecha límite");
  });
});
