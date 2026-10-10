import { describe, expect, it } from "vitest";
import { orderPlanA, proposalFor, stockIssue, stockLine, wasteIssue } from "../test/copilotFixtures";
import { buildDecisionItems, deadlineText, tierLabel } from "./copilot";

const SIM = "2026-07-19";
const build = (over: Partial<Parameters<typeof buildDecisionItems>[0]> = {}) =>
  buildDecisionItems({ issues: [wasteIssue], plan: orderPlanA, proposals: [], simToday: SIM, ...over });

describe("buildDecisionItems", () => {
  it("puts issues with a N2/N3 recommended option under approvals and order-plan lines under technical", () => {
    const items = build();
    expect(items.map((i) => [i.id, i.kind])).toEqual([
      [stockIssue.issue_id, "tech"],
      [wasteIssue.issue_id, "approval"],
    ]);
  });

  it("sends an issue whose recommended option is N1 to the technical list", () => {
    const n1 = { ...wasteIssue, options: wasteIssue.options!.map((o) => (o.option_id === "65ead6dcd46e" ? { ...o, tier: "N1" } : o)) };
    expect(build({ issues: [n1], plan: null })[0].kind).toBe("tech");
  });

  it("does not repeat an issue that is also an order-plan line, and skips integrity and do-nothing issues", () => {
    const integrity = { ...wasteIssue, issue_id: "i-int", integrity: true };
    const idle = { ...wasteIssue, issue_id: "i-idle", recommended_option_id: "a0f43dce40dc" };
    const items = build({ issues: [stockIssue, integrity, idle] });
    expect(items.map((i) => i.id)).toEqual([stockIssue.issue_id]);
  });

  it("hides items already decided in this case and keeps the pending proposal id", () => {
    expect(build({ proposals: [proposalFor(wasteIssue.issue_id, "approved")] }).map((i) => i.id)).toEqual([stockIssue.issue_id]);
    const pending = build({ proposals: [proposalFor(wasteIssue.issue_id)] }).find((i) => i.id === wasteIssue.issue_id);
    expect(pending?.proposalId).toBe("pp1");
  });

  it("marks a line without issue as read-only", () => {
    const items = build({ issues: [], plan: { ...orderPlanA, lines: [{ ...stockLine, issue: null }] } });
    expect(items[0]).toMatchObject({ id: "line|SKU-100263", readOnly: true, optionId: "" });
  });

  it("builds the technical card from the order-plan line, in Spanish, with backend numbers only", () => {
    const t = build()[0];
    expect(t).toMatchObject({
      optionId: "8f63a675ef2b", actionType: "place_order", tier: "N2", level: "N2 · Propuesta",
      title: "Comprar 1 caja de Md Choc Stout C.B. Wsweet Cold Foam",
      supplier: "Summit Frozen Foods", arrive: "llega mar 21", cost: "$14.60",
      value: "+$38.43 a $45.00", impact: "Riesgo de quiebre 100% → 40%", deadline: "Hoy", confPct: "41%",
      icon: "shopping_basket",
    });
    expect(t.warn).toContain("Pedido bajo el mínimo de $300.00");
    expect(t.warn).toContain("Confianza limitada (41%)");
    expect(t.why).toContain("Quiebre proyectado: mar 21");
  });

  it("builds the approval card from the issue", () => {
    const a = build()[1];
    expect(a).toMatchObject({ title: "Omitir el pedido de 12 Croiss-Ant Donuts", level: "N2 · Propuesta", value: "+$58.92", confPct: "74%", deadline: "Hoy", impact: "Merma evitada ~$58.92" });
    expect(a.summary).toContain("Merma de $638.30");
  });

  it("fills the analysis sections for an approval and the dialogue sections for a technical decision", () => {
    const [t, a] = build();
    expect(a.sections.map((s) => s.label)).toEqual(["Problema", "Recomendación", "Pros", "Contras", "Requiere tu aprobación"]);
    expect(t.sections.map((s) => s.label)).toEqual(["Por qué", "Si aceptas", "Si no actúas", "Alternativas"]);
    expect(a.sections.find((s) => s.label === "Contras")!.items).toContain("Skipping an order can cause a stockout before the next delivery.");
    expect(t.sections.find((s) => s.label === "Si no actúas")!.items).toEqual(["Costo de no actuar: $53.52"]);
    expect(t.sections.find((s) => s.label === "Alternativas")!.items).toEqual(["Sin alternativas propuestas por el sistema."]);
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
