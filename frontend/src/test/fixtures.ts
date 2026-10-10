import type { DaySummary, ForecastResponse } from "../types";

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
