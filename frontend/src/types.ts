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
