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

// ---- Sucursal (real shapes, S030 / case date 2026-07-19) ----
import type { DaySummary, DeliveriesResponse, ExpiringResponse, ForecastResponse, InventoryResponse, Kpis } from "../types";

const fp = (date: string, forecast: number, p10: number, p90: number) => ({ date, forecast, p10, p90, baseline: forecast, actual: null, censored: false });
export const branchForecast: ForecastResponse = {
  store_id: "S030", sku: null, level: "store", as_of: "2026-07-19", forecast_origin: "2026-07-19", model: "glm_poisson", model_version: "file", unit: "usd", horizon_days: 2,
  points: [
    { ...fp("2026-07-18", 654.4479, 540.1, 790.9), actual: 849.2 },
    { ...fp("2026-07-19", 868.5446, 700.2, 1100.8), actual: 1135.18 },
    fp("2026-07-20", 833.3911, 681.7231, 1060.493),
  ],
  metrics_to_date: { wape: 0, bias: 0, coverage_p10_p90: 0, wape_baseline: 0, n_days: 0 },
};
export const ayerSummary: DaySummary = {
  store_id: "S030", date: "2026-07-18", as_of: "2026-07-19",
  totals: { footfall: 734, transactions: 105, units_sold: 171, net_sales: 849.2, staff_hours: 37.6 },
  context: { weekday: "Sat", is_weekend: true, is_holiday: false, holiday_name: null, is_school_break: true, weather: { temp_max_c: 37.2, temp_min_c: 29.2, precip_mm: 4.6 } },
  vs_same_weekday_avg: { baseline_net_sales: 677.87, weeks_used: 7, delta_pct: 25.3 },
};
export const hoySummary: DaySummary = {
  store_id: "S030", date: "2026-07-19", as_of: "2026-07-19",
  totals: { footfall: 965, transactions: 116, units_sold: 216, net_sales: 1135.18, staff_hours: 40.6 },
  context: { weekday: "Sun", is_weekend: true, is_holiday: false, holiday_name: null, is_school_break: true, weather: { temp_max_c: 35, temp_min_c: 28, precip_mm: 0 } },
  vs_same_weekday_avg: { baseline_net_sales: 700, weeks_used: 7, delta_pct: 62 },
};
export const branchKpis: Kpis = {
  as_of: "2026-07-19", net_sales: 6450.2, transactions: 751, conversion: 0.1164, waste_usd: 1202.09,
  lost_sales_usd: { low: 74.93, mid: 534.62, high: 690.63 }, window: { from: "2026-07-13", to: "2026-07-19" },
};
export const branchExpiring: ExpiringResponse = {
  as_of: "2026-07-19", total_waste_usd: { low: 48.18, mid: 60.53, high: 71.9 },
  by_day: [{ date: "2026-07-20", waste_usd: { low: 10.5, mid: 12.25, high: 15 }, projected: true }, { date: "2026-07-21", waste_usd: { low: 47.49, mid: 59.03, high: 69.82 }, projected: true }],
};
export const branchInventory: InventoryResponse = {
  as_of: "2026-07-19",
  items: [
    { sku: "SKU-100263", product_name: "Md Choc Stout C.B. Wsweet Cold Foam", on_hand: 5, avg_daily_demand: 3.23, days_of_cover: 1.5, projected_stockout_date: "2026-07-21" },
    { sku: "SKU-100014", product_name: "Bagel Twist Sour C And Onion", on_hand: 0, avg_daily_demand: 1.12, days_of_cover: 0, projected_stockout_date: "2026-07-30" },
  ],
};
export const branchDeliveries: DeliveriesResponse = {
  as_of: "2026-07-19",
  days: [
    { date: "2026-07-19", projected: false, deliveries: [
      { supplier_id: "SUP01", supplier_name: "Northfield Bakery Partners", po_id: "PO1", kind: "open_po", lines: [{ sku: "SKU-100170", product_name: "Croiss-Ant Donuts", qty: 12 }], expected_date: "2026-07-19", status: "on_time" },
      { supplier_id: "SUP05", supplier_name: "Pioneer Merch & Packaging", po_id: "PO2", kind: "open_po", lines: [{ sku: "SKU-9", product_name: "Vasos 12 oz", qty: 40 }], expected_date: "2026-07-16", status: "late" },
    ] },
    { date: "2026-07-21", projected: true, deliveries: [
      { supplier_id: "SUP03", supplier_name: "Summit Frozen Foods", po_id: "PO3", kind: "open_po", lines: [{ sku: "SKU-100030", product_name: "Southwestern Veggie Burrito", qty: 10 }], expected_date: "2026-07-21", status: "expected", projected: true },
      { supplier_id: "SUP03", supplier_name: "Summit Frozen Foods", po_id: "S1", kind: "scheduled", lines: [], expected_date: "2026-07-21", status: "expected", projected: true },
    ] },
  ],
};

// ---- Memorias / Advertencias (real shapes) ----
import type { AlertRecord, HistoryResponse, Issue as IssueT, SupplierPerformance } from "../types";

export const historyA: HistoryResponse = {
  as_of: "2026-07-19",
  decision_log: [
    { decision_id: "d1", issue_id: "S030|overstock_waste|SKU-100473", kind: "overstock_waste", sku: null, action_type: "skip_order", tier: "N2", status: "rejected", rationale: "t", reason: "Prefiero quedarme corto", created_at: "2026-10-10T05:55:37Z" },
    { decision_id: "d2", issue_id: "S030|overstock_waste|SKU-100502", kind: "overstock_waste", sku: "SKU-100502", action_type: "skip_order", tier: "N2", status: "approved", rationale: "t", reason: "", created_at: "2026-10-09T05:55:02Z" },
    { decision_id: "d3", issue_id: "S030|calendar_uplift", kind: "calendar_uplift", sku: null, action_type: "adjust_order_qty", tier: "N2", status: "approved", rationale: "", reason: "", created_at: "2026-10-08T05:55:02Z" },
    { decision_id: "d4", issue_id: "S030|overstock_waste|SKU-100304", kind: "overstock_waste", sku: "SKU-100304", action_type: "place_order", tier: "N2", status: "pending", rationale: "", reason: "", created_at: "2026-10-07T05:55:02Z" },
  ],
};
export const suppliersA: SupplierPerformance[] = [
  { supplier_id: "SUP03", supplier_name: "Summit Frozen Foods", received_pos: 667, lead_time_mean_days: 2.17, on_time_pct: 90.1, fill_pct: 99.9, window_days: 180 },
];
export const alertsA: AlertRecord[] = [
  { alert_id: "al1", alert_type: 1, store_id: "S030", case_id: "x", severity_usd: 687.4, state: "nueva", as_of: "2026-03-11", category: "operacion", agent_id: "present", ts: "2026-10-10T07:10:00Z", issue: { kind: "overstock_waste", sku: "SKU-100502", product_name: "12 Croiss-Ant Donuts" } },
  { alert_id: "al2", alert_type: 19, store_id: "S030", case_id: "x", severity_usd: 202.9, state: "nueva", as_of: "2026-03-14", category: "operacion", agent_id: "present", ts: "2026-10-10T06:00:00Z", issue: { kind: "calendar_uplift", event: { name: "School break" } } as never },
  { alert_id: "al3", alert_type: 21, store_id: "S030", case_id: "x", severity_usd: 58.92, state: "nueva", as_of: "2026-05-30", category: "automatica", agent_id: "sentinel", ts: "2026-10-10T05:30:00Z", issue: { kind: "compliance_deviation" } },
];
export const integrityA: IssueT[] = [
  { issue_id: "S030|orphan_sku|SKU-7xxxxx", kind: "orphan_sku", integrity: true, category: "integrity", exposure_usd: 14537.12, as_of: "2026-07-19" } as IssueT,
];

// ---- Wave 14 (real shapes: GET /cases/fce42dd29fba/decisions/pending and /issues/{id}/analysis, S030, 2026-07-19) ----
import type { IssueAnalysis, PendingResponse } from "../types";

export const pendingA: PendingResponse = {
  as_of: "2026-07-19",
  store_id: "S030",
  approvals: [
    {
      issue_id: "S030|overstock_waste|SKU-100502", title: "Sobreinventario y merma: 12 Croiss-Ant Donuts", tier: "N2", deadline: "2026-07-19",
      impact_usd: { low: 58.92, mid: 58.92, high: 58.92 }, confidence: { score: 0.7416, calibrated: true },
      problem: "Se recibe más 12 Croiss-Ant Donuts del que se vende y la merma de los últimos 14 días fue de $638.",
      recommendation: { option_id: "65ead6dcd46e", label: "Omitir el pedido de 12 Croiss-Ant Donuts en este ciclo", action_type: "skip_order", params: { sku: "SKU-100502" } },
      requires_approval: true, kind: "overstock_waste", sku: "SKU-100502", product_name: "12 Croiss-Ant Donuts",
    },
  ],
  technical: [
    {
      issue_id: "S030|stockout_risk|SKU-100263", option_id: "8f63a675ef2b", sku: "SKU-100263", product_name: "Md Choc Stout C.B. Wsweet Cold Foam", supplier_id: "SUP03",
      supplier_name: "Summit Frozen Foods", qty: 10, expected_delivery: "2026-07-21", cost_usd: { low: 14.6, mid: 14.6, high: 14.6 },
      why: "Md Choc Stout C.B. Wsweet Cold Foam se agotaría el 2026-07-21 sin pedido; el pedido llega el 2026-07-21.",
      impact_chips: ["Venta perdida esperada $10.63", "Merma esperada $0.96", "Riesgo de desabasto sin pedido 100%"], deadline: "2026-07-19", confidence: 0.4094, tier: "N2",
      label: "Pedir 10 unidades de Md Choc Stout C.B. Wsweet Cold Foam",
      warning: "El pedido a Summit Frozen Foods ($106) está por debajo del mínimo del proveedor ($300); conviene consolidarlo con la siguiente entrega. Es un aviso, no un bloqueo.",
      warning_codes: ["below_min_order"],
    },
  ],
};

export const analysisApproval: IssueAnalysis = {
  issue_id: "S030|overstock_waste|SKU-100502", title: "Sobreinventario y merma: 12 Croiss-Ant Donuts", tier: "N2", deadline: "2026-07-19",
  impact_usd: { low: 58.92, mid: 58.92, high: 58.92 }, confidence: { score: 0.7416, calibrated: true },
  problem: "Se recibe más 12 Croiss-Ant Donuts del que se vende y la merma de los últimos 14 días fue de $638.",
  recommendation: { option_id: "65ead6dcd46e", label: "Omitir el pedido de 12 Croiss-Ant Donuts en este ciclo", action_type: "skip_order", params: {} },
  pros: ["Reduce la merma en $58.92.", "Respaldado por 538 casos de backtest (confianza 74%)."],
  cons: ["Omitir el pedido puede causar un desabasto antes de la próxima entrega."], requires_approval: true,
  dialog: {
    why: "Es la opción con mayor efecto neto esperado ($58.92) frente a no hacer nada, que cuesta $112.",
    if_accept: "Si apruebas: Omitir el pedido de 12 Croiss-Ant Donuts en este ciclo.", if_not_act: "Si no actúas: pérdida esperada $112 (merma $112).",
    alternatives: [{ option_id: "a0f43dce40dc", label: "No hacer nada", net_usd_mid: 0 }],
  },
};

// ---- GET /cases/d17217ea4550/memories (real shapes) ----
import type { MemoryRecord } from "../types";

export const memoriesA: MemoryRecord[] = [
  { memory_id: "rej-7d7ee16b9f3a", category: "preferencias", text: "Rechazaste omitir el pedido de 6 Bacon Donuts el 2026-07-19: «Este proveedor siempre llega tarde» (motivo: otro).", source: "rejection_reason", cases_count: 1, verified: false, created_at: "2026-10-10T11:10:18.710389+00:00", new: true },
  { memory_id: "dec-3c379580f251", category: "proveedores", text: "Aprobaste omitir el pedido de 12 Croiss-Ant Donuts el 2026-07-19.", source: "decision_log", cases_count: 3, verified: true, created_at: "2026-10-09T09:00:00+00:00", new: false },
  { memory_id: "bb-1", category: "demanda", text: "La dona glaseada recibe 1.9 veces lo que vende.", source: "backboard", cases_count: 1, verified: false, created_at: "2026-10-01T09:00:00+00:00", new: false },
  { memory_id: "bb-2", category: "eventos", text: "Bloqueo del 14 de marzo: -38% de afluencia.", source: "backboard", cases_count: 1, verified: true, created_at: "2026-09-01T09:00:00+00:00", new: false },
];

export const agentsA = [
  { agent_id: "present", display_name_es: "Analista del presente", status: "up" as const },
  { agent_id: "sentinel", display_name_es: "Centinela", status: "up" as const },
];
