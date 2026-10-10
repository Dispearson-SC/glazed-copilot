// Types mirror the public API contract (snake_case, ISO dates).
export interface Store {
  store_id: string;
  name: string;
  format: string;
  site_id: string;
  region: string;
  site_name?: string;
  site_type?: string;
  display_name?: string;
}

/** What users see: site and store, never the code. */
export const storeLabel = (s: Pick<Store, "name" | "display_name">): string => s.display_name || s.name;

export type CaseMode = "live" | "sandbox" | "backtest";

export interface Case {
  case_id: string;
  store_id: string;
  sim_today: string;
  mode: CaseMode;
  parent_case_id: string | null;
  core_conversation_id: string | null;
  title: string;
  created_at: string;
}

export interface Alert {
  alert_id: string;
  alert_type: number;
  store_id: string;
  case_id: string;
  severity_usd: number;
  state: string;
  issue: Partial<Issue> & Record<string, unknown>;
  issue_key: string;
  as_of: string;
  created_at: string;
}

export interface Proposal {
  proposal_id: string;
  case_id: string;
  store_id: string;
  issue_id: string;
  action_type: string;
  params: Record<string, unknown>;
  tier: string;
  rationale: string;
  status: string;
  reason: string;
  reason_category?: string | null;
  reason_confidence?: number | null;
  agent_id: string;
  created_at: string;
}

export interface Execution {
  execution_id: string;
  proposal_id: string;
  case_id: string;
  source: string;
  status: string;
  detail: string;
  executed_at: string;
}

export type TurnStatus = "pending" | "done" | "failed" | "waiting_approval";

export interface ReplyMeta {
  source: "fast" | "agents";
  template?: string;
  elapsed_ms: number;
}

export interface Turn {
  turn_id: string;
  status: TurnStatus;
  reply?: string | null;
  error?: string | null;
  still_running?: boolean;
  sanitized?: boolean;
  sanitized_fragments?: string[];
  reply_meta?: ReplyMeta | null;
}

export type TraceKind = "message" | "tool_call" | "tool_result" | "escalation";

export interface TraceEvent {
  event_id?: string;
  case_id: string;
  store_id: string;
  ts: string;
  from_agent: string;
  to_agent: string;
  kind: TraceKind;
  payload: Record<string, unknown>;
}

// ---- Wave 5: deterministic issues and options ----
export interface Range3 {
  low: number;
  mid: number;
  high: number;
}

export type Tier = "N0" | "N1" | "N2" | "N3";

export interface Evidence {
  metric: string;
  value: number | string;
  unit: string;
  period: string;
  source: string;
}

export interface Option {
  option_id: string;
  action_type: string;
  params: Record<string, unknown>;
  expected_benefit_usd: Range3;
  cost_usd: number;
  net_usd_mid: number;
  loss_impact: { waste_usd_delta: number; lost_sales_usd_delta: number };
  confidence: { score: number; n_backtest: number; method: string };
  tier: Tier;
  tier_reasons: string[];
  urgency: { deadline_date?: string | null; reason: string };
  risk: string[];
  if_act: string | null;
  if_not: string | null;
}

export interface Issue {
  issue_id: string;
  kind: string;
  sku?: string;
  supplier_id?: string;
  store_id: string;
  store_display_name: string;
  as_of: string;
  severity_usd: number;
  category?: string | null;
  exposure_usd?: number | null;
  evidence: Evidence[];
  data_caveats: string[];
  options: Option[];
}

export interface OrderLine {
  sku: string;
  name?: string;
  supplier_id: string;
  supplier_name?: string;
  qty: number;
  qty_low?: number;
  qty_high?: number;
  case_size?: number;
  cases?: number;
  service_level_target: number;
  order_deadline: string | null;
  projected_stockout_date: string | null;
  stockout_risk_without_order: number;
  vs_current_practice: { received_to_sold: number; qty_delta: number };
  min_order_warning: string | MinOrderWarning | null;
  /** Legacy fixtures send a number; the live route sends {low,mid,high}. */
  expected_waste_usd?: number | Range3;
  expected_lost_sales_usd?: number | Range3;
  est_cost_usd?: number;
  expected_delivery?: string | null;
  order_deadline_status?: string;
  stockout_risk_with_order?: number;
  issue?: Issue;
}

export interface MinOrderWarning {
  min_order_value: number;
  order_value_usd: number;
  suggestion?: string;
}

export interface PlanSupplier {
  supplier_id: string;
  supplier_name: string;
  order_value_usd: number;
  min_order_value: number;
}

export interface OrderPlan {
  case_id: string;
  store_id: string;
  as_of: string;
  lines: OrderLine[];
  suppliers?: PlanSupplier[];
}

export interface Kpis {
  waste_usd: number | Range3;
  lost_sales_usd: Range3;
  window?: { from: string; to: string };
}

export interface AdvanceResult {
  sim_today: string;
  new_alerts: Alert[];
}

// ---- Wave 6: Sentinel (Centinela) ----
export type ExecutionStatus = "executed" | "not_executed" | "partial";
export type Diagnosis = "not_executed" | "within_range" | "external_event" | "forecast_error";

export interface ComplianceRecord {
  decision_id: string;
  issue_id: string | null;
  action_type: string | null;
  status: string;
  applicable: boolean;
  execution: { status: string; source: string; detail?: string; executed_at?: string } | null;
  execution_status: ExecutionStatus | null;
  horizon: { decision_date: string; days: number; ends: string; passed: boolean } | null;
  simulated: { net_usd_mid: number; net_usd_low?: number | null; net_usd_high?: number | null; label: string } | null;
  observed: { net_usd: number; label: string } | null;
  events: { type: string; date_from: string; date_to: string; note?: string }[];
  diagnosis: Diagnosis | null;
  explanation: string;
}

export type InjectBody =
  | { execution: { proposal_id: string; status: "not_executed" | "partial"; detail?: string } }
  | { event: { type: string; date_from: string; date_to?: string; note?: string } };

// ---- Dashboard: day summary and briefing (any field may be missing or null) ----
export interface DayTotals {
  footfall?: number | null;
  transactions?: number | null;
  units_sold?: number | null;
  net_sales?: number | null;
  staff_hours?: number | null;
}

export interface DaySummary {
  store_id: string;
  date: string;
  as_of: string;
  /** null = the store has no data for that day (HTTP 200, not an error). */
  totals: DayTotals | null;
  by_department?: { department: string; net_sales: number; units: number }[];
  top_skus?: { sku: string; product_name: string; net_sales: number; units: number }[];
  context?: {
    weekday?: string;
    is_weekend?: boolean;
    is_holiday?: boolean;
    holiday_name?: string | null;
    is_school_break?: boolean;
    /** Observed weather of that day, not a forecast. */
    weather?: { temp_max_c?: number | null; temp_min_c?: number | null; precip_mm?: number | null } | null;
  };
  vs_same_weekday_avg?: { baseline_net_sales: number; weeks_used: number; delta_pct: number } | null;
  store_display_name?: string;
}

export interface HeadlineItem {
  key: string;
  text: string;
  value?: number | null;
  unit?: string;
  source?: string;
  low?: number;
  high?: number;
}

/** A line of the briefing's order_plan summary (due_today / due_tomorrow / top_lines). */
export interface BriefOrderLine {
  sku?: string;
  name?: string;
  supplier_id?: string;
  supplier_name?: string;
  qty?: number;
  cases?: number;
  est_cost_usd?: number;
  expected_delivery?: string | null;
  projected_stockout_date?: string | null;
  order_deadline?: string | null;
  order_deadline_status?: string;
  stockout_risk_without_order?: number;
  below_min_order?: boolean;
}

export interface BriefSupplier {
  supplier_id: string;
  supplier_name?: string;
  on_time_pct?: number | null;
  fill_pct?: number | null;
  next_delivery?: string | null;
}

export interface Briefing {
  snapshot?: {
    as_of?: string;
    kpis?: { lost_sales_usd?: Range3 | null } & Record<string, unknown>;
    order_plan?: {
      due_today?: BriefOrderLine[];
      due_tomorrow?: BriefOrderLine[];
      top_lines?: BriefOrderLine[];
      total_lines?: number;
      deadline_passed?: number;
    };
    suppliers?: BriefSupplier[];
  };
  headline?: HeadlineItem[];
  suggested_focus?: string[];
}

// ---- Manager-day: forecast (Wave 11). Contract agreed with Core; route may not be deployed. ----
export interface ForecastPoint {
  date: string;
  forecast: number;
  p10: number;
  p90: number;
  baseline: number;
  /** null for dates after as_of: the UI never shows actuals past as_of. */
  actual: number | null;
  censored: boolean;
  stockout_hours?: number;
  quantiles?: Record<string, number>;
}

export interface ForecastMetrics {
  wape: number;
  bias: number;
  coverage_p10_p90: number;
  wape_baseline: number;
  n_days: number;
  pinball_074?: number | null;
  censored_coverage?: number | null;
  censored_pinball_074?: number | null;
  /** Stockout-censored days: shown apart and not counted as misses. */
  n_censored?: number;
}

export type AccuracyBy = "shelf_life" | "format" | "sku";

export interface ForecastAccuracy {
  store_id: string;
  by: AccuracyBy;
  as_of: string;
  window: { from: string; to: string };
  unit: string;
  model: string;
  groups: Record<string, ForecastMetrics>;
  overall: ForecastMetrics;
}

export interface ForecastResponse {
  store_id: string;
  sku: string | null;
  level: "sku" | "store";
  as_of: string;
  forecast_origin: string;
  model: string;
  model_version: string;
  unit: string;
  horizon_days: number;
  points: ForecastPoint[];
  metrics_to_date: ForecastMetrics;
  projected?: boolean;
}

// ---- Manager-day: decisions timeline (Wave 11) ----
// The route answers a flat, ts-ordered list of rows (proposal -> decision -> execution -> outcome).
export type DecisionKind = "proposal" | "decision" | "execution" | "outcome" | "skip_order";

export interface DecisionOutcome {
  observed: { net_usd?: number; waste_usd?: number; lost_sales_usd?: number } & Record<string, unknown>;
  simulated: { net_usd_mid: number; net_usd_low?: number | null; net_usd_high?: number | null; label?: string } & Record<string, unknown>;
  label: string;
  score?: { within_expected_range?: boolean; error_vs_mid_usd?: number; diagnosis?: string };
}

export interface DecisionRow {
  decision_id: string;
  ts: string;
  kind: DecisionKind;
  issue_id: string;
  action_type: string;
  sku?: string;
  supplier?: string;
  qty?: number;
  deadline?: string;
  status: string;
  reason?: string;
  reason_category?: string;
  /** Outcome rows: the end of the measured horizon. */
  as_of?: string;
  outcome?: DecisionOutcome;
}

// ---- Manager-day: stored conversation (Wave 11 GET /cases/{id}/turns) ----
export interface TurnRecord {
  turn_id: string;
  ts: string;
  user_text: string;
  /** Full stored final reply; null while the turn is in flight. */
  reply: string | null;
  status: TurnStatus;
  error?: string | null;
  still_running?: boolean;
  reply_meta?: ReplyMeta | null;
}

// ---- Manager-day: Wave 12 (inventory, expiring, deliveries, promos, staffing). Contracts agreed with Core. ----
export interface InventoryItem {
  sku: string;
  product_name: string;
  department: string;
  on_hand: number;
  avg_daily_demand: number;
  days_of_cover: number | null;
  turnover_28d: number | null;
  weeks_of_supply: number | null;
  inventory_value_usd: number;
  last_sale_date: string | null;
  slow_mover: boolean;
  projected_stockout_date: string | null;
}

export type InventorySort = "days_of_cover" | "turnover" | "slow";

export interface InventoryResponse {
  as_of?: string;
  coverage: { skus_with_inventory: number; skus_selling: number };
  items: InventoryItem[];
}

export interface ExpiringItem {
  sku: string;
  product_name: string;
  expiring_units: number;
  expiry_date: string;
  shelf_life_days: number;
  waste_usd: Range3;
  lot_age_inferred: boolean;
}

export interface ExpiringResponse {
  as_of?: string;
  items: ExpiringItem[];
  by_day: { date: string; waste_usd: number }[];
  total_waste_usd: number | Range3;
}

export interface DeliveryEntry {
  supplier_id: string;
  supplier_name: string;
  po_id: string | null;
  kind: "open_po" | "scheduled";
  lines: { sku: string; product_name: string; qty: number }[];
  value_usd: number;
  status: "on_time" | "late" | "expected";
}

export interface DeliveriesResponse {
  as_of?: string;
  days: { date: string; deliveries: DeliveryEntry[] }[];
}

export interface Promo {
  promo_id: string;
  name: string;
  department: string;
  discount_pct: number;
  start_date: string;
  end_date: string;
  status: "active" | "upcoming" | "past";
  audit_verdict: string | null;
  evaluation: { uplift_pct: number } | null;
}

export interface PromosResponse {
  as_of?: string;
  items: Promo[];
}

export interface StaffingDay {
  date: string;
  forecast_transactions: number;
  recommended_staff_hours: number;
  planned_staff_hours: number | null;
  gap_hours: number | null;
  basis: "daily";
}

export interface StaffingResponse {
  as_of?: string;
  benchmark: { format: string; tx_per_staff_hour_p50: number };
  days: StaffingDay[];
  note: string;
}
