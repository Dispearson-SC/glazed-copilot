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

export interface Turn {
  turn_id: string;
  status: TurnStatus;
  reply?: string | null;
  error?: string | null;
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
  min_order_warning: string | null;
  expected_waste_usd?: number;
  expected_lost_sales_usd?: number;
  issue?: Issue;
}

export interface OrderPlan {
  case_id: string;
  store_id: string;
  as_of: string;
  lines: OrderLine[];
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
