import type { Issue, OrderLine, OrderPlan, Proposal } from "../types";

// Trimmed copies of real GET /cases/fce42dd29fba/{issues,order-plan} responses (S030, 2026-07-19).
export const wasteIssue: Issue = {
  issue_id: "S030|overstock_waste|SKU-100502", kind: "overstock_waste", sku: "SKU-100502", product_name: "12 Croiss-Ant Donuts",
  supplier_id: "SUP01", as_of: "2026-07-19", severity_usd: 638.3,
  evidence: [
    { metric: "waste_usd_14d", value: 638.3, unit: "USD", period: "last 14 days" },
    { metric: "received_28d", value: 312, unit: "units", period: "last 28 days" },
    { metric: "sold_28d", value: 27, unit: "units", period: "last 28 days" },
  ],
  options: [
    { option_id: "65ead6dcd46e", action_type: "skip_order", params: { sku: "SKU-100502", supplier_id: "SUP01", cycle_date: "2026-07-19", typical_qty: 12 },
      expected_benefit_usd: { low: 58.92, mid: 58.92, high: 58.92 }, cost_usd: 0, net_usd_mid: 58.92,
      loss_impact: { waste_usd_delta: -58.92, lost_sales_usd_delta: 0 }, confidence: { score: 0.7416, n_backtest: 538, method: "backtest_replay" },
      tier: "N2", tier_reasons: ["proposal: skip_order is not an auto-executable action; calibrated confidence 0.74 < 0.85"],
      urgency: { deadline_date: "2026-07-19", reason: "Applies to the next order for this SKU." },
      risk: ["Skipping an order can cause a stockout before the next delivery."], if_act: null, if_not: null },
    { option_id: "a0f43dce40dc", action_type: "do_nothing", params: {}, expected_benefit_usd: { low: 0, mid: 0, high: 0 }, cost_usd: 112.32,
      loss_impact: { waste_usd_delta: 112.32, lost_sales_usd_delta: 0 }, confidence: { score: 1, method: "baseline" }, tier: "N0",
      urgency: { deadline_date: null, reason: "Expected waste per cycle if the current order size continues." }, risk: [], cost_of_inaction_usd: { mid: 112.32 } },
  ],
  recommended_option_id: "65ead6dcd46e",
};

export const stockIssue: Issue = {
  issue_id: "S030|stockout_risk|SKU-100263", kind: "stockout_risk", sku: "SKU-100263", product_name: "Md Choc Stout C.B. Wsweet Cold Foam",
  supplier_id: "SUP03", as_of: "2026-07-19", severity_usd: 53.52, evidence: [{ metric: "closing_qty", value: 5, unit: "units", period: "2026-07-19" }],
  options: [
    { option_id: "8f63a675ef2b", action_type: "place_order", params: { sku: "SKU-100263", supplier_id: "SUP03", qty: 10, cases: 1, case_size: 10 },
      expected_benefit_usd: { low: 38.43, mid: 42.89, high: 45 }, cost_usd: 14.6, net_usd_mid: 28.29,
      loss_impact: { waste_usd_delta: 0.96, lost_sales_usd_delta: -42.89 }, confidence: { score: 0.4094, n_backtest: 127, method: "backtest_replay" },
      tier: "N2", tier_reasons: ["proposal: calibrated confidence 0.41 < 0.85"],
      urgency: { deadline_date: "2026-07-19", reason: "Order by 2026-07-19 to land before the projected stockout on 2026-07-21." },
      risk: ["May leave ~$0.96 of waste."], if_act: null, if_not: null },
    { option_id: "f5f2ffbcd45e", action_type: "do_nothing", params: {}, expected_benefit_usd: { low: 0, mid: 0, high: 0 }, cost_usd: 53.52,
      loss_impact: { waste_usd_delta: 0, lost_sales_usd_delta: 53.52 }, confidence: { score: 1, method: "baseline" }, tier: "N0",
      urgency: { deadline_date: null, reason: "Expected lost sales if no order is placed." }, risk: [], cost_of_inaction_usd: { mid: 53.52 } },
  ],
  recommended_option_id: "8f63a675ef2b",
};

export const stockLine: OrderLine = {
  sku: "SKU-100263", name: "Md Choc Stout C.B. Wsweet Cold Foam", product_name: "Md Choc Stout C.B. Wsweet Cold Foam", supplier_id: "SUP03",
  supplier_name: "Summit Frozen Foods", qty: 10, cases: 1, case_size: 10, est_cost_usd: 14.6, expected_delivery: "2026-07-21", usable_stock: 2.5,
  projected_stockout_date: "2026-07-21", order_deadline: "2026-07-19", stockout_risk_without_order: 0.9971, stockout_risk_with_order: 0.4001,
  min_order_warning: { min_order_value: 300, order_value_usd: 106.1 }, issue: stockIssue,
};

export const orderPlanA: OrderPlan = { store_id: "S030", as_of: "2026-07-19", total_lines: 1, lines: [stockLine], case_id: "c1" };

export const proposalFor = (issue_id: string, status = "pending"): Proposal => ({
  proposal_id: "pp1", case_id: "c1", store_id: "S030", issue_id, action_type: "place_order", params: {}, tier: "N2",
  rationale: "", status, reason: "", agent_id: "", created_at: "2026-07-19T08:00:00Z",
});
