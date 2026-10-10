import type { Api } from "../api";
import { usd, weekdayDay } from "../format";
import type { AlertRecord, Issue, IssueOption, OrderLine, OrderPlan, Proposal } from "../types";

/**
 * Copilot view models. Types only plus pure adapters from the public API shapes:
 * the app ships no sample data, every value comes from the backend or is shown as "Sin datos".
 */

export type Tab = "agente" | "decisiones" | "sucursal" | "memorias" | "alertas";
export type DayKey = "ayer" | "hoy" | "manana";
export type MemoryCategory = "proveedores" | "demanda" | "eventos" | "preferencias";

export interface Memory {
  id: string;
  cat: MemoryCategory;
  /** Material Symbols icon name. */
  icon: string;
  tag: string;
  text: string;
  src: string;
  conf: string;
  isNew?: boolean;
}

/** An analysis or dialogue card shown in the chat, anchored after `at` chat messages. */
export interface AnalysisRef {
  id: string;
  itemId: string;
  mode: "analizar" | "dialogo";
  at: number;
}

/** The decision or warning the chat is currently about ("Hablando de: …"). */
export interface CopilotContext {
  id: string;
  title: string;
}

// ---------------------------------------------------------------------------------------------
// Data sources. Each source is ONE function so swapping it for the real route is a one-line change.
// `{status: "soon"}` means the backend route does not exist yet: the UI shows "Disponible pronto".
// See the GAP LIST in odd/tasks/copiloto.md for the suggested contracts.
// ---------------------------------------------------------------------------------------------

export type Source<T> = { status: "ok"; data: T } | { status: "soon" };
const SOON = { status: "soon" } as const;
export const SOON_TEXT = "Disponible pronto";

export interface ChatContext {
  issueId: string;
  optionId?: string;
  title: string;
  mode: "analizar" | "dialogo" | "advertencia";
}

/** POST /cases/{id}/messages with `context:{issue_id, option_id?, mode}` is pending: the context travels inside the text. */
export function chatContextText(text: string, ctx: ChatContext | null): string {
  return ctx ? `Contexto: ${ctx.title} (${ctx.issueId}).\n${text}` : text;
}

/** GET /cases/{id}/issues/{issue_id}/analysis (pending): sections are built locally from the issue meanwhile. */
export const fetchIssueAnalysis = async (_api: Api, _caseId: string, _issueId: string): Promise<Source<never>> => SOON;
/** /forecast?metric=traffic|weather (pending). */
export const fetchForecastMetric = async (_api: Api, _caseId: string, _metric: string): Promise<Source<never>> => SOON;
/** /inventory status fields: critical / follow-up / ok (pending). */
export const fetchInventoryStatus = async (_api: Api, _caseId: string): Promise<Source<never>> => SOON;
/** GET /cases/{id}/memories (pending). */
export const fetchMemories = async (_api: Api, _caseId: string): Promise<Source<never>> => SOON;
/** GET /cases/{id}/autonomy/log (pending). */
export const fetchAutonomyLog = async (_api: Api, _caseId: string): Promise<Source<never>> => SOON;
/** POST /cases/{id}/autonomy/{action_id}/revert (pending). */
export const revertAutonomy = async (_api: Api, _caseId: string, _actionId: string): Promise<Source<never>> => SOON;
/** GET /agents/status (pending). */
export const fetchAgentsStatus = async (_api: Api): Promise<Source<never>> => SOON;
/** Turn `progress[]` (pending). */
export const fetchTurnProgress = async (_api: Api, _caseId: string, _turnId: string): Promise<Source<never>> => SOON;
/** GET /cases/{id}/inbox-counts (pending): badges are counted from the loaded lists meanwhile. */
export const fetchInboxCounts = async (_api: Api, _caseId: string): Promise<Source<never>> => SOON;
/** Alert `agent_id` / `category` (pending on /alerts). */
export const alertAgent = (a: AlertRecord): string | null => (a as { agent_id?: string }).agent_id ?? null;

// ---------------------------------------------------------------------------------------------
// Decisions: GET /cases/{id}/issues + GET /cases/{id}/order-plan + GET /proposals -> cards.
// The UI never computes: it only formats backend values and picks wording by action type.
// ---------------------------------------------------------------------------------------------
export interface AnalysisSection {
  label: string;
  icon: string;
  /** Hex color of the section title. */
  color: string;
  items: string[];
}

export interface DecisionItem {
  /** issue_id, or `line|<sku>` for an order-plan line without an issue. */
  id: string;
  issueId: string;
  /** Recommended option; "" when the line cannot be decided through proposals. */
  optionId: string;
  /** Existing pending proposal for this issue, reused instead of creating a new one. */
  proposalId?: string;
  kind: "approval" | "tech";
  readOnly: boolean;
  actionType: string;
  tier: string;
  icon: string;
  level: string;
  title: string;
  summary: string;
  /** Expected benefit range, e.g. "+$38.43 a $45.00". */
  value: string;
  conf: number;
  confPct: string;
  deadline: string;
  supplier: string;
  arrive: string;
  cost: string;
  why: string;
  impact: string;
  warn: string;
  sections: AnalysisSection[];
}

const TIER_NAMES: Record<string, string> = { N1: "Automática", N2: "Propuesta", N3: "Diálogo" };
export const tierLabel = (tier: string): string => (TIER_NAMES[tier] ? `${tier} · ${TIER_NAMES[tier]}` : tier);

export function deadlineText(deadline: string | null | undefined, simToday: string): string {
  if (!deadline) return "Sin fecha límite";
  if (deadline === simToday) return "Hoy";
  return deadline > simToday ? `Antes del ${weekdayDay(deadline)}` : `Venció ${weekdayDay(deadline)}`;
}

const pct = (n: number): string => `${Math.round(n * 100)}%`;
const NONE = ["Sin datos"];
const ACTION_ICONS: Record<string, string> = {
  place_order: "shopping_basket",
  skip_order: "remove_shopping_cart",
  adjust_order_qty: "tune",
  markdown_end_of_day: "sell",
  transfer: "swap_horiz",
};

function actionTitle(o: IssueOption, issue: Issue): string {
  const product = issue.product_name || issue.sku || issue.kind;
  const p = o.params as { cases?: number; qty?: number; event?: string };
  switch (o.action_type) {
    case "place_order":
      return p.cases ? `Comprar ${p.cases} ${p.cases === 1 ? "caja" : "cajas"} de ${product}` : `Comprar ${p.qty ?? ""} pzas de ${product}`.replace("  ", " ");
    case "skip_order":
      return `Omitir el pedido de ${product}`;
    case "adjust_order_qty":
      return p.event ? `Ajustar el pedido por ${p.event}` : `Ajustar el pedido de ${product}`;
    case "markdown_end_of_day":
      return `Descuento al cierre en ${product}`;
    case "transfer":
      return `Transferir ${product}`;
    default:
      return `${o.action_type} · ${product}`;
  }
}

function benefitText(o: IssueOption): string {
  const b = o.expected_benefit_usd;
  if (!b) return "";
  const { low, mid, high } = b;
  if (low != null && high != null && low !== high) return `+${usd(low)} a ${usd(high)}`;
  const one = mid ?? low ?? high;
  return one ? `+${usd(one)}` : "";
}

const evidence = (issue: Issue, metric: string): number | string | undefined => issue.evidence?.find((e) => e.metric === metric)?.value;

function impactText(o: IssueOption, line?: OrderLine): string {
  if (line?.stockout_risk_without_order != null && line.stockout_risk_with_order != null)
    return `Riesgo de quiebre ${pct(line.stockout_risk_without_order)} → ${pct(line.stockout_risk_with_order)}`;
  const waste = o.loss_impact?.waste_usd_delta;
  const lost = o.loss_impact?.lost_sales_usd_delta;
  if (waste != null && waste < 0) return `Merma evitada ~${usd(-waste)}`;
  if (lost != null && lost < 0) return `Venta recuperada ~${usd(-lost)}`;
  return "";
}

function whyText(o: IssueOption, issue: Issue, line?: OrderLine): string {
  if (line?.usable_stock != null && line.expected_delivery) {
    const out = line.projected_stockout_date ? ` Quiebre proyectado: ${weekdayDay(line.projected_stockout_date)}.` : "";
    return `Stock utilizable ${line.usable_stock}; el próximo reparto llega el ${weekdayDay(line.expected_delivery)}.${out}`;
  }
  const waste = evidence(issue, "waste_usd_14d");
  if (typeof waste === "number") {
    const rec = evidence(issue, "received_28d");
    const sold = evidence(issue, "sold_28d");
    const flow = rec != null && sold != null ? `; se recibieron ${rec} y se vendieron ${sold} en 28 días` : "";
    return `Merma de ${usd(waste)} en 14 días${flow}.`;
  }
  return o.urgency?.reason ?? "";
}

function warnText(o: IssueOption, line?: OrderLine): string {
  const out: string[] = [];
  if (line?.min_order_warning)
    out.push(`Pedido bajo el mínimo de ${usd(line.min_order_warning.min_order_value)} del proveedor (pedido: ${usd(line.min_order_warning.order_value_usd)}): considera consolidar.`);
  const c = o.confidence;
  if (c && c.score < 0.5) out.push(`Confianza limitada (${pct(c.score)})${c.n_backtest ? `: ${c.n_backtest} casos de validación` : ""}.`);
  return out.join(" ");
}

const sec = (label: string, icon: string, color: string, items: string[]): AnalysisSection => ({ label, icon, color, items: items.filter(Boolean).length ? items.filter(Boolean) : NONE });

function sectionsFor(kind: "approval" | "tech", o: IssueOption, issue: Issue, f: { title: string; why: string; impact: string; value: string }): AnalysisSection[] {
  const inaction = issue.options?.find((x) => x.action_type === "do_nothing");
  const others = (issue.options ?? []).filter((x) => x.option_id !== o.option_id && x.action_type !== "do_nothing");
  if (kind === "approval")
    return [
      sec("Problema", "report", "#7a5649", [f.why]),
      sec("Recomendación", "recommend", "#331b11", [f.title, o.urgency?.reason ?? ""]),
      sec("Pros", "add_circle", "#cb9564", [f.value && `Beneficio esperado: ${f.value}`, f.impact]),
      sec("Contras", "remove_circle", "#82746f", [...(o.risk ?? []), o.cost_usd ? `Costo: ${usd(o.cost_usd)}` : ""]),
      sec("Requiere tu aprobación", "how_to_reg", "#4b3025", o.tier_reasons ?? []),
    ];
  const cost = inaction?.cost_of_inaction_usd?.mid ?? inaction?.cost_usd;
  const waste = o.loss_impact?.waste_usd_delta;
  return [
    sec("Por qué", "help", "#7a5649", [f.why]),
    sec("Si aceptas", "check_circle", "#cb9564", [f.impact, f.value && `Beneficio esperado: ${f.value}`, waste != null && waste > 0 ? `Merma esperada: +${usd(waste)}` : ""]),
    sec("Si no actúas", "block", "#82746f", [o.if_not ?? "", cost ? `Costo de no actuar: ${usd(cost)}` : ""]),
    sec("Alternativas", "alt_route", "#331b11", others.length ? others.map((x) => actionTitle(x, issue)) : ["Sin alternativas propuestas por el sistema."]),
  ];
}

function toItem(issue: Issue, line: OrderLine | undefined, kind: "approval" | "tech", o: IssueOption, proposals: Proposal[], simToday: string): DecisionItem {
  const title = actionTitle(o, issue);
  const why = whyText(o, issue, line);
  const impact = impactText(o, line);
  const value = benefitText(o);
  const conf = o.confidence?.score ?? 0;
  const pending = proposals.find((p) => p.issue_id === issue.issue_id && p.status === "pending");
  const cost = line?.est_cost_usd ?? o.cost_usd;
  return {
    id: issue.issue_id,
    issueId: issue.issue_id,
    optionId: o.option_id,
    ...(pending ? { proposalId: pending.proposal_id } : {}),
    kind,
    readOnly: false,
    actionType: o.action_type,
    tier: o.tier,
    icon: ACTION_ICONS[o.action_type] ?? "bolt",
    level: tierLabel(o.tier),
    title,
    summary: why,
    value,
    conf,
    confPct: pct(conf),
    deadline: deadlineText(o.urgency?.deadline_date, simToday),
    supplier: line?.supplier_name ?? issue.supplier_id ?? "",
    arrive: line?.expected_delivery ? `llega ${weekdayDay(line.expected_delivery)}` : "",
    cost: cost ? usd(cost) : "",
    why,
    impact,
    warn: warnText(o, line),
    sections: sectionsFor(kind, o, issue, { title, why, impact, value }),
  };
}

const recommended = (issue: Issue): IssueOption | undefined =>
  issue.options?.find((o) => o.option_id === issue.recommended_option_id) ?? issue.options?.find((o) => o.action_type !== "do_nothing");

/**
 * Approvals: issues (GET /issues) whose recommended option is N2/N3. Technical: order-plan lines plus issue options with tier N1.
 * Items already decided for this case are hidden; a pending proposal is reused. Tiers come from the backend.
 */
export function buildDecisionItems(input: { issues: Issue[]; plan: OrderPlan | null; proposals: Proposal[]; simToday: string }): DecisionItem[] {
  const { issues, plan, proposals, simToday } = input;
  const decided = new Set(proposals.filter((p) => p.status !== "pending").map((p) => p.issue_id));
  const seen = new Set<string>();
  const out: DecisionItem[] = [];
  for (const line of plan?.lines ?? []) {
    const issue = line.issue;
    const o = issue && recommended(issue);
    if (!issue || !o || o.action_type === "do_nothing") {
      out.push(readOnlyLine(line, simToday));
      continue;
    }
    seen.add(issue.issue_id);
    if (decided.has(issue.issue_id)) continue;
    out.push(toItem(issue, line, "tech", o, proposals, simToday));
  }
  for (const issue of issues) {
    if (seen.has(issue.issue_id) || issue.integrity || issue.category === "integrity" || decided.has(issue.issue_id)) continue;
    const o = recommended(issue);
    if (!o || o.action_type === "do_nothing") continue;
    out.push(toItem(issue, undefined, o.tier === "N1" ? "tech" : "approval", o, proposals, simToday));
  }
  return out.sort((a, b) => (a.kind === b.kind ? 0 : a.kind === "tech" ? -1 : 1));
}

function readOnlyLine(line: OrderLine, simToday: string): DecisionItem {
  const product = line.product_name || line.name || line.sku;
  return {
    id: `line|${line.sku}`, issueId: "", optionId: "", kind: "tech", readOnly: true, actionType: "place_order", tier: "", icon: "shopping_basket",
    level: "", title: `Comprar ${line.qty ?? ""} pzas de ${product}`.replace("  ", " "), summary: "", value: "", conf: 0, confPct: "Sin datos", deadline: deadlineText(line.order_deadline, simToday),
    supplier: line.supplier_name ?? line.supplier_id ?? "", arrive: line.expected_delivery ? `llega ${weekdayDay(line.expected_delivery)}` : "",
    cost: line.est_cost_usd ? usd(line.est_cost_usd) : "", why: "", impact: "", warn: "", sections: [],
  };
}
