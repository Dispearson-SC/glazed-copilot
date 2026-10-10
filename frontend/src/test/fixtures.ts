import type { Issue, Kpis, Option, OrderPlan } from "../types";

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
