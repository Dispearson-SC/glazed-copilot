import { describe, expect, it } from "vitest";
import type { AlertRecord } from "../types";
import { pendingA } from "../test/copilotFixtures";
import { buildPendingItems, buildWarnings } from "./copilot";

const alert = (over: Partial<AlertRecord>): AlertRecord => ({ alert_id: "a1", alert_type: 2, store_id: "S001", case_id: "c1", state: "nueva", ...over });

describe("alert labels in Spanish", () => {
  it("uses title_es from the backend", () => {
    const [w] = buildWarnings({ alerts: [alert({ title_es: "Riesgo de desabasto: Angus SteakSandwich", kind_label_es: "Riesgo de desabasto", issue: { kind: "stockout_risk" } })], integrity: [] });
    expect(w.title).toBe("Riesgo de desabasto: Angus SteakSandwich");
  });

  it("never shows a raw kind when the Spanish fields are missing", () => {
    const ws = buildWarnings({ alerts: [alert({ issue: { kind: "stockout_risk" } }), alert({ alert_id: "a2", issue: { kind: "something_new" } })], integrity: [] });
    expect(ws.map((w) => w.title)).toEqual(["Riesgo de desabasto", "Advertencia"]);
  });
});

describe("decision dedupe", () => {
  it("shows one card per issue_id when it arrives as technical and approval", () => {
    const base = buildPendingItems(pendingA, "2026-07-19");
    const approval = pendingA.approvals[0];
    const dup = { ...pendingA, technical: [...pendingA.technical, { ...pendingA.technical[0], issue_id: approval.issue_id, option_id: approval.recommendation.option_id }] };
    const items = buildPendingItems(dup, "2026-07-19");
    expect(items.length).toBe(base.length);
    expect(items.filter((i) => i.id === approval.issue_id)).toHaveLength(1);
    expect(items.find((i) => i.id === approval.issue_id)?.kind).toBe("approval");
  });
});
