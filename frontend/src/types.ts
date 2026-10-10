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
  /** Optional ISO dates; absent in the current payload. */
  closed_on?: string | null;
  opened_on?: string | null;
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
  issue_key?: string | null;
  archived?: boolean;
}

/** POST /cases/{id}/advance. `outcomes` lists decisions whose result became measurable. */
export interface AdvanceResult {
  sim_today: string;
  new_alerts: unknown[];
  outcomes: unknown[];
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
  source?: "fast" | "agents";
  template?: string;
  elapsed_ms?: number;
  /** The issue context echoed by the backend. */
  context?: { issue_id: string; option_id?: string | null; mode: "analizar" | "dialogo" };
}

/** `context` of POST /cases/{id}/messages. */
export interface MessageContext {
  issue_id: string;
  option_id?: string;
  mode: "analizar" | "dialogo";
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
  /** Agents the orchestrator is consulting; present on every read of a turn. */
  progress?: TurnProgress[];
}

export interface TurnProgress {
  agent_id: string;
  display_name_es: string;
  state: "consulting" | "done";
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

// ---- Dashboard: day summary (any field may be missing or null) ----
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

// ---- Forecast. The route may not be deployed (404/501) or may fail; the dashboard degrades to actuals only. ----
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
  /** True for dates after as_of. */
  projected?: boolean;
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
  /** Present on `?metric=` reads. */
  metric?: string;
  /** `conversion` reads: false when the footfall counter was unreliable. */
  conversion_valid?: boolean | null;
  unit_label?: string;
}

// ---- Manager-day: stored conversation (GET /cases/{id}/turns) ----
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

// ---- Copilot: issues, order plan, alerts (public API, case scoped) ----
export interface Range3 {
  low?: number | null;
  mid?: number | null;
  high?: number | null;
}

export interface IssueOption {
  option_id: string;
  action_type: string;
  params: Record<string, unknown>;
  expected_benefit_usd?: Range3 | null;
  cost_usd?: number | null;
  net_usd_mid?: number | null;
  loss_impact?: { waste_usd_delta?: number | null; lost_sales_usd_delta?: number | null } | null;
  confidence?: { score: number; n_backtest?: number; method?: string } | null;
  tier: string;
  tier_reasons?: string[];
  urgency?: { deadline_date: string | null; reason?: string } | null;
  risk?: string[];
  if_act?: string | null;
  if_not?: string | null;
  cost_of_inaction_usd?: { mid?: number | null } | null;
}

export interface IssueEvidence {
  metric: string;
  value: number | string;
  unit?: string;
  period?: string;
}

export interface Issue {
  issue_id: string;
  kind: string;
  sku?: string | null;
  product_name?: string | null;
  supplier_id?: string | null;
  as_of?: string;
  severity_usd?: number | null;
  category?: string;
  integrity?: boolean;
  evidence?: IssueEvidence[];
  options?: IssueOption[];
  recommended_option_id?: string | null;
  exposure_usd?: number | null;
  event?: { name?: string; type?: string; days?: string[] } | null;
}

export interface OrderLine {
  sku: string;
  product_name?: string;
  name?: string;
  supplier_id?: string;
  supplier_name?: string;
  qty?: number;
  cases?: number;
  case_size?: number;
  est_cost_usd?: number | null;
  expected_delivery?: string | null;
  usable_stock?: number | null;
  projected_stockout_date?: string | null;
  order_deadline?: string | null;
  stockout_risk_without_order?: number | null;
  stockout_risk_with_order?: number | null;
  min_order_warning?: { min_order_value: number; order_value_usd: number } | null;
  /** The decidable issue of this line; absent = the line cannot go through proposals. */
  issue?: Issue | null;
}

export interface OrderPlan {
  store_id: string;
  as_of: string;
  total_lines: number;
  lines: OrderLine[];
  case_id?: string;
}

export interface AlertRecord {
  alert_id: string;
  alert_type: number;
  store_id: string;
  case_id: string;
  severity_usd?: number | null;
  state: string;
  as_of?: string;
  created_at?: string;
  issue_key?: string;
  /** operacion | integridad | automatica */
  category?: string;
  agent_id?: string;
  ts?: string;
  /** Spanish kind label and title from the backend ("Riesgo de desabasto", "Riesgo de desabasto: Angus SteakSandwich"). */
  kind_label_es?: string;
  title_es?: string;
  issue?: (Partial<Issue> & { options?: IssueOption[] }) | null;
}

// ---- Sucursal window: kpis, expiring, inventory, deliveries ----
export interface Kpis {
  as_of: string;
  days_with_data?: number;
  net_sales?: number | null;
  transactions?: number | null;
  conversion?: number | null;
  waste_usd?: number | null;
  lost_sales_usd?: Range3 | null;
  window?: { from: string; to: string };
}

export interface ExpiringResponse {
  as_of: string;
  total_waste_usd?: Range3 | null;
  by_day?: { date: string; waste_usd: Range3; projected?: boolean }[];
}

export interface InventoryItem {
  sku: string;
  product_name: string;
  department?: string;
  on_hand: number;
  avg_daily_demand: number;
  days_of_cover: number | null;
  projected_stockout_date?: string | null;
  status?: "critical" | "watch" | "ok";
  status_reason?: string;
  forecast_outflow_units?: number | null;
  scheduled_in_units?: number | null;
  next_delivery_date?: string | null;
  closing_reason?: "sold_out" | "discarded_perishable" | "in_stock" | "no_movement";
  /** Backend sentence that explains the closing stock, e.g. "Agotado hoy (6.9 h sin stock) · llegan 40 mañana". */
  display_status_es?: string;
}

export interface InventoryResponse {
  as_of: string;
  /** Days covered by `forecast_outflow_units`. */
  outflow_days?: number;
  items: InventoryItem[];
}

export interface DeliveryRow {
  supplier_id: string;
  supplier_name: string;
  po_id: string;
  kind: string;
  lines: { sku: string; product_name: string; qty: number }[];
  value_usd?: number;
  expected_date: string;
  status: string;
  projected?: boolean;
}

export interface DeliveriesResponse {
  as_of: string;
  days: { date: string; projected: boolean; deliveries: DeliveryRow[] }[];
}

/** GET /cases/{id}/outlook?days=2: next-days expectations (verified against the live backend). */
export interface OutlookDay {
  date: string;
  net_sales?: Range3 | null;
  transactions?: Range3 | null;
  avg_ticket?: Range3 | null;
  expected_waste_usd?: Range3 | null;
  expected_lost_sales_usd?: Range3 | null;
  weather?: null;
  weather_note?: string;
  projected?: boolean;
}

export interface Outlook {
  as_of?: string;
  days: OutlookDay[];
}

// ---- Memorias / Advertencias ----
export interface DecisionLogEntry {
  decision_id: string;
  issue_id: string;
  kind?: string;
  sku?: string | null;
  action_type: string;
  tier?: string;
  status: string;
  rationale?: string;
  reason?: string;
  created_at: string;
}

export interface HistoryResponse {
  as_of: string;
  decision_log: DecisionLogEntry[];
}

export interface SupplierPerformance {
  supplier_id: string;
  supplier_name: string;
  received_pos: number;
  lead_time_mean_days: number;
  on_time_pct: number;
  fill_pct: number;
  window_days: number;
}

// ---- Wave 14: pending decisions, analysis, atomic decision, memories, agents ----
export interface PendingApproval {
  issue_id: string;
  title: string;
  tier: string;
  deadline: string | null;
  impact_usd: Range3;
  confidence: { score: number | null; calibrated: boolean };
  problem: string;
  recommendation: { option_id: string; label: string; action_type: string; params: Record<string, unknown> };
  requires_approval: boolean;
  kind?: string;
  kinds?: string[];
  merged_issue_ids?: string[];
  sku?: string | null;
  product_name?: string | null;
}

export interface PendingTechnical {
  /** null when the plan line has no decidable issue. */
  issue_id: string | null;
  option_id: string | null;
  sku: string;
  product_name?: string | null;
  supplier_id?: string | null;
  supplier_name?: string | null;
  qty?: number | null;
  expected_delivery?: string | null;
  cost_usd: Range3;
  why: string;
  impact_chips: string[];
  deadline: string | null;
  /** Wave 15: {score, calibrated}; older backends send a bare number. */
  confidence: number | { score: number | null; calibrated?: boolean } | null;
  tier: string | null;
  label: string;
  warning?: string;
  warning_codes?: string[];
}

/** GET /cases/{id}/decisions/pending */
export interface PendingResponse {
  as_of: string;
  store_id: string;
  approvals: PendingApproval[];
  technical: PendingTechnical[];
}

/** GET /cases/{id}/issues/{issue_id}/analysis (Spanish, built by the backend). */
export interface IssueAnalysis {
  issue_id: string;
  title: string;
  tier: string;
  deadline: string | null;
  impact_usd: Range3;
  confidence: { score: number | null; calibrated: boolean };
  problem: string;
  recommendation: { option_id: string; label: string; action_type: string; params: Record<string, unknown> };
  pros: string[];
  cons: string[];
  requires_approval: boolean;
  dialog: { why: string; if_accept: string; if_not_act: string; alternatives: { option_id: string; label: string; net_usd_mid: number | null }[] };
}

/** POST /cases/{id}/decisions */
export interface CaseDecisionBody {
  issue_id: string;
  option_id: string;
  approved: boolean;
  reason?: string;
}

export interface CaseDecisionResult {
  decision_id: string;
  proposal_id: string;
  status: string;
  reason_category?: string;
  idempotent_replay?: boolean;
}

/** GET /cases/{id}/memories */
export interface MemoryRecord {
  memory_id: string;
  category: string;
  text: string;
  source: string;
  cases_count: number;
  verified: boolean;
  created_at: string;
  /** Created less than 24 hours ago. */
  new: boolean;
}

export interface AgentStatus {
  agent_id: string;
  display_name_es: string;
  status: "up" | "degraded" | "down";
}

/** GET /agents/status: every agent shares the Core state. */
export interface AgentsStatusResponse {
  connected: boolean;
  agents: AgentStatus[];
}

/** GET /cases/{id}/inbox-counts */
export interface InboxCounts {
  approvals: number;
  technical: number;
  alerts: number;
}
