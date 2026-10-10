import type { Briefing, DaySummary, ForecastResponse, Issue, Kpis, Option, OrderPlan } from "../types";

const base = {
  cost_usd: 0,
  confidence: { score: 0.8, n_backtest: 12, method: "backtest_replay" },
  tier_reasons: [] as string[],
  urgency: { deadline_date: null, reason: "" },
  risk: [] as string[],
  if_act: null,
  if_not: null,
  params: {},
  loss_impact: { waste_usd_delta: 0, lost_sales_usd_delta: 0 },
  expected_benefit_usd: { low: 0, mid: 0, high: 0 },
};

export const optDoNothing: Option = {
  ...base, option_id: "o-nothing", action_type: "do_nothing", net_usd_mid: -120, tier: "N1",
  expected_benefit_usd: { low: 0, mid: 0, high: 0 },
  loss_impact: { waste_usd_delta: 0, lost_sales_usd_delta: 120 },
};
export const optN0: Option = {
  ...base, option_id: "o-n0", action_type: "transfer_stock", net_usd_mid: 500, tier: "N0",
  tier_reasons: ["datos insuficientes"],
};
export const optN2: Option = {
  ...base, option_id: "o-n2", action_type: "place_order", net_usd_mid: 80, tier: "N2",
  tier_reasons: ["monto sobre umbral"], confidence: { score: 0.4, n_backtest: 3, method: "backtest_replay" },
  expected_benefit_usd: { low: 20, mid: 90, high: 160 },
  loss_impact: { waste_usd_delta: 10, lost_sales_usd_delta: -100 },
  urgency: { deadline_date: "2026-03-02", reason: "proveedor cierra mañana" },
  risk: ["sobrante si baja la demanda"],
};
export const optN3: Option = {
  ...base, option_id: "o-n3", action_type: "run_promo", net_usd_mid: 150, tier: "N3",
  tier_reasons: ["cambia precio"],
};

export const issueA: Issue = {
  issue_id: "i1", kind: "stockout_risk", sku: "DONUT-GLZ", store_id: "S030",
  store_display_name: "Aeropuerto Norte · Glazed Centro", as_of: "2026-03-01", severity_usd: 150,
  evidence: [{ metric: "ventas_diarias", value: 42, unit: "pzas", period: "últimos 14 días", source: "sales" }],
  data_caveats: ["sin datos de merma de la semana pasada"],
  options: [optDoNothing, optN0, optN2, optN3],
};

export const kpisA: Kpis = {
  waste_usd: 310.5,
  lost_sales_usd: { low: 100, mid: 180.25, high: 260 },
  window: { from: "2026-02-15", to: "2026-03-01" },
};

export const planA: OrderPlan = {
  case_id: "c1", store_id: "S030", as_of: "2026-03-01",
  lines: [
    {
      sku: "DONUT-GLZ", name: "Dona glaseada", supplier_id: "SUP1", supplier_name: "Panificadora Norte",
      qty: 48, qty_low: 36, qty_high: 60, case_size: 12, cases: 4, service_level_target: 0.95,
      order_deadline: "2026-03-01", projected_stockout_date: "2026-03-03", stockout_risk_without_order: 0.72,
      vs_current_practice: { received_to_sold: 1.4, qty_delta: -8 }, min_order_warning: "Pedido mínimo $200",
      expected_waste_usd: 20, expected_lost_sales_usd: 60, issue: issueA,
    },
    {
      sku: "MUFFIN", name: "Muffin", supplier_id: "SUP2", supplier_name: "Harinas del Sur",
      qty: 24, case_size: 6, cases: 4, service_level_target: 0.9,
      order_deadline: "2026-03-09", projected_stockout_date: "2026-03-12", stockout_risk_without_order: 0.1,
      vs_current_practice: { received_to_sold: 0.9, qty_delta: 2 }, min_order_warning: null,
    },
  ],
};

export const daySummaryA: DaySummary = {
  store_id: "S030", date: "2026-03-10", as_of: "2026-03-11",
  totals: { footfall: 852, transactions: 74, units_sold: 138, net_sales: 733.91, staff_hours: 36.2 },
  by_department: [{ department: "Beverage", net_sales: 379.08, units: 70 }],
  top_skus: [
    { sku: "SKU-1", product_name: "50 Donut Holes", net_sales: 105, units: 5 },
    { sku: "SKU-2", product_name: "Frozen Blend Lg", net_sales: 92.17, units: 13 },
    { sku: "SKU-3", product_name: "Vanilla Chai", net_sales: 45.43, units: 7 },
    { sku: "SKU-4", product_name: "Cuarto lugar", net_sales: 40, units: 2 },
  ],
  context: {
    weekday: "Tue", is_weekend: false, is_holiday: true, holiday_name: "Día de prueba", is_school_break: false,
    weather: { temp_max_c: 24.7, temp_min_c: 16.7, precip_mm: 0 },
  },
  vs_same_weekday_avg: { baseline_net_sales: 617.92, weeks_used: 8, delta_pct: 18.8 },
  store_display_name: "Aeropuerto Norte · Glazed Centro",
};

export const briefingA: Briefing = {
  snapshot: {
    as_of: "2026-03-11",
    kpis: { lost_sales_usd: { low: 39.62, mid: 430.77, high: 565.38 } },
    order_plan: { due_today: [{}], due_tomorrow: [{}, {}], top_lines: [], total_lines: 5, deadline_passed: 1 },
  },
  headline: [
    { key: "waste_7d", text: "Merma 7 días $1,361", value: 1360.94, unit: "USD" },
    { key: "lost_sales", text: "Venta perdida estimada $40–$565", value: 430.77, unit: "USD", low: 39.62, high: 565.38 },
  ],
  suggested_focus: ["i1", "i2"],
};

// Shapes captured from the live backend (case at 2026-07-19, store S030).
export const briefingLive: Briefing = {
  snapshot: {
    as_of: "2026-07-19",
    order_plan: {
      due_today: [
        { sku: "SKU-1", name: "Cold Foam", supplier_id: "SUP03", supplier_name: "Summit Frozen Foods", qty: 10, cases: 1, est_cost_usd: 14.6,
          expected_delivery: "2026-07-21", projected_stockout_date: "2026-07-21", order_deadline: "2026-07-19", order_deadline_status: "ok",
          stockout_risk_without_order: 0.9971, below_min_order: true },
        { sku: "SKU-2", name: "Sand", supplier_id: "SUP03", supplier_name: "Summit Frozen Foods", qty: 10, cases: 1, est_cost_usd: 19.7,
          expected_delivery: "2026-07-21", projected_stockout_date: "2026-07-22", order_deadline: "2026-07-19", order_deadline_status: "ok",
          stockout_risk_without_order: 0.84, below_min_order: true },
      ],
      due_tomorrow: [
        { sku: "SKU-3", name: "Coffee Beans", supplier_id: "SUP06", supplier_name: "Evergreen Coffee Roasters", qty: 5, cases: 1, est_cost_usd: 16.5,
          expected_delivery: "2026-07-22", projected_stockout_date: "2026-07-23", order_deadline: "2026-07-20", order_deadline_status: "ok",
          stockout_risk_without_order: 0.5, below_min_order: true },
      ],
      top_lines: [],
      total_lines: 3,
      deadline_passed: 0,
    },
    suppliers: [
      { supplier_id: "SUP01", supplier_name: "Northfield Bakery Partners", on_time_pct: 92.7, fill_pct: 100, next_delivery: "2026-07-20" },
      { supplier_id: "SUP03", supplier_name: "Summit Frozen Foods", on_time_pct: 90.1, fill_pct: 99.9, next_delivery: "2026-07-21" },
    ],
  },
  headline: [
    { key: "orders_due_today", text: "2 pedidos vencen hoy", value: 2, unit: "pedidos" },
    { key: "worst_supplier", text: "Proveedor con menor puntualidad: Pioneer Merch & Packaging (85.7%)", value: 85.7, unit: "%" },
  ],
  suggested_focus: [],
};

export const planLive: OrderPlan = {
  case_id: "c1", store_id: "S030", as_of: "2026-07-19",
  suppliers: [
    { supplier_id: "SUP03", supplier_name: "Summit Frozen Foods", order_value_usd: 106.1, min_order_value: 300 },
    { supplier_id: "SUP06", supplier_name: "Evergreen Coffee Roasters", order_value_usd: 16.5, min_order_value: 350 },
  ],
  lines: [
    { sku: "SKU-1", name: "Cold Foam", supplier_id: "SUP03", supplier_name: "Summit Frozen Foods", qty: 10, cases: 1, case_size: 10,
      service_level_target: 0.68, est_cost_usd: 14.6, expected_delivery: "2026-07-21", order_deadline: "2026-07-19", order_deadline_status: "ok",
      projected_stockout_date: "2026-07-21", stockout_risk_without_order: 0.9971, stockout_risk_with_order: 0.4001,
      expected_waste_usd: { low: 0.29, mid: 0.96, high: 2.38 }, expected_lost_sales_usd: { low: 4.84, mid: 10.63, high: 18.78 },
      vs_current_practice: { received_to_sold: 1.25, qty_delta: 0 },
      min_order_warning: { min_order_value: 300, order_value_usd: 106.1, suggestion: "Below the supplier minimum" } },
    { sku: "SKU-2", name: "Sand", supplier_id: "SUP03", supplier_name: "Summit Frozen Foods", qty: 10, cases: 1, case_size: 10,
      service_level_target: 0.7, est_cost_usd: 19.7, expected_delivery: "2026-07-21", order_deadline: "2026-07-19", order_deadline_status: "ok",
      projected_stockout_date: "2026-07-22", stockout_risk_without_order: 0.84, stockout_risk_with_order: 0.3,
      expected_waste_usd: { low: 0.1, mid: 0.5, high: 1 }, expected_lost_sales_usd: { low: 1, mid: 2, high: 3 },
      vs_current_practice: { received_to_sold: 1, qty_delta: 0 }, min_order_warning: null },
    { sku: "SKU-9", name: "Never runs out", supplier_id: "SUP06", supplier_name: "Evergreen Coffee Roasters", qty: 5, cases: 1, case_size: 5,
      service_level_target: 0.9, est_cost_usd: 16.5, expected_delivery: "2026-07-22", order_deadline: "2026-07-20", order_deadline_status: "ok",
      projected_stockout_date: null, stockout_risk_without_order: 0.01, stockout_risk_with_order: 0,
      expected_waste_usd: { low: 0, mid: 0, high: 0 }, expected_lost_sales_usd: { low: 0, mid: 0, high: 0 },
      vs_current_practice: { received_to_sold: 1, qty_delta: 0 }, min_order_warning: null },
  ],
};

export const forecastA: ForecastResponse = {
  store_id: "S030", sku: null, level: "store", as_of: "2026-03-01", forecast_origin: "2026-03-01",
  model: "baseline-weekday-8w", model_version: "1", unit: "USD", horizon_days: 7,
  points: [
    { date: "2026-02-27", forecast: 90, p10: 70, p90: 110, baseline: 88, actual: 95, censored: false },
    { date: "2026-02-28", forecast: 100, p10: 80, p90: 120, baseline: 98, actual: 60, censored: true, stockout_hours: 5 },
    { date: "2026-03-01", forecast: 110, p10: 90, p90: 130, baseline: 105, actual: 112, censored: false },
    { date: "2026-03-02", forecast: 120, p10: 95, p90: 150, baseline: 115, actual: null, censored: false },
    { date: "2026-03-03", forecast: 80, p10: 60, p90: 100, baseline: 82, actual: 999, censored: false },
  ],
  metrics_to_date: { wape: 0.123, bias: -0.021, coverage_p10_p90: 0.8, wape_baseline: 0.2, n_days: 28, n_censored: 3 },
};

import type { DecisionRow } from "../types";
export const decisionsA: DecisionRow[] = [
  { decision_id: "p1", ts: "2026-02-20T08:00:00Z", kind: "proposal", status: "proposed", issue_id: "i1", action_type: "place_order", sku: "DONUT-GLZ", supplier: "SUP1", qty: 48, deadline: "2026-02-21" },
  { decision_id: "p1", ts: "2026-02-20T09:00:00Z", kind: "decision", status: "approved", issue_id: "i1", action_type: "place_order", sku: "DONUT-GLZ", reason: "Va la promo" },
  { decision_id: "p1", ts: "2026-02-20T09:00:01Z", kind: "execution", status: "executed", issue_id: "i1", action_type: "place_order", sku: "DONUT-GLZ" },
  { decision_id: "p1", ts: "2026-02-28T00:00:00Z", kind: "outcome", status: "measured", as_of: "2026-02-27", issue_id: "i1", action_type: "place_order", sku: "DONUT-GLZ",
    outcome: { observed: { net_usd: 55 }, simulated: { net_usd_mid: 80, net_usd_low: 20, net_usd_high: 160, label: "backtest" }, label: "backtest",
      score: { within_expected_range: true, error_vs_mid_usd: -25, diagnosis: "within_range" } } },
  { decision_id: "p2", ts: "2026-02-25T08:00:00Z", kind: "proposal", status: "proposed", issue_id: "i2", action_type: "skip_order", sku: "MUFFIN" },
  { decision_id: "p2", ts: "2026-02-25T08:30:00Z", kind: "skip_order", status: "approved", issue_id: "i2", action_type: "skip_order", sku: "MUFFIN" },
  { decision_id: "p3", ts: "2026-02-26T08:00:00Z", kind: "proposal", status: "proposed", issue_id: "i3", action_type: "run_promo" },
  { decision_id: "p3", ts: "2026-02-26T08:10:00Z", kind: "decision", status: "rejected", issue_id: "i3", action_type: "run_promo", reason: "Sin presupuesto" },
  { decision_id: "p4", ts: "2026-03-05T08:00:00Z", kind: "outcome", status: "measured", as_of: "2026-03-04", issue_id: "i4", action_type: "place_order",
    outcome: { observed: { net_usd: 999 }, simulated: { net_usd_mid: 10 }, label: "backtest" } },
];

import type { ForecastAccuracy } from "../types";
const m = (wape: number, n_days: number, n_censored: number) => ({ wape, bias: -0.1, coverage_p10_p90: 0.78, wape_baseline: wape, n_days, n_censored });
export const accuracyA: ForecastAccuracy = {
  store_id: "S030", by: "shelf_life", as_of: "2026-03-01", window: { from: "2026-02-01", to: "2026-03-01" }, unit: "units", model: "baseline-weekday-8w",
  groups: { "1": m(0.4243, 176, 18), "2-3": m(0.4889, 571, 121), "4-14": m(1.1736, 27, 1), non_perishable: m(0.6855, 179, 14) },
  overall: m(0.4959, 953, 154),
};
