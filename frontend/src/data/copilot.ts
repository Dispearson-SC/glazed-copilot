import { isUnavailable, type Api } from "../api";
import { avgTicket, dayMonth, longDate, shiftDate, signedPct, usd, usdWhole, weekdayDay } from "../format";
import type {
  AlertRecord, DaySummary, DeliveriesResponse, ExpiringResponse, ForecastResponse, InventoryResponse, Issue, IssueAnalysis, Kpis, OrderPlan,
  DecisionLogEntry, HistoryResponse, Outlook, OutlookDay, PendingResponse, Range3, SupplierPerformance,
} from "../types";

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
// Decisions: GET /cases/{id}/decisions/pending -> cards. The UI never computes: it formats backend values.
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
  /** Option to decide; "" when the line cannot be decided. */
  optionId: string;
  kind: "approval" | "tech";
  readOnly: boolean;
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
  /** Backend impact chips (technical cards). */
  chips: string[];
  warn: string;
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

function benefitText(r: Range3 | null | undefined): string {
  if (!r) return "";
  const { low, mid, high } = r;
  if (low != null && high != null && low !== high) return `+${usd(low)} a ${usd(high)}`;
  const one = mid ?? low ?? high;
  return one ? `+${usd(one)}` : "";
}

const confText = (score: number | null | undefined): string => (score == null ? "Sin datos" : pct(score));

/** Maps GET /decisions/pending to cards. Approvals and technical come split by the backend; a technical line with no issue/option is read-only. */
export function buildPendingItems(pending: PendingResponse | null, simToday: string): DecisionItem[] {
  if (!pending) return [];
  const approvals = pending.approvals.map((a): DecisionItem => ({
    id: a.issue_id, issueId: a.issue_id, optionId: a.recommendation.option_id, kind: "approval", readOnly: false, tier: a.tier,
    icon: ACTION_ICONS[a.recommendation.action_type] ?? "bolt", level: tierLabel(a.tier), title: a.recommendation.label, summary: a.problem,
    value: benefitText(a.impact_usd), conf: a.confidence.score ?? 0, confPct: confText(a.confidence.score), deadline: deadlineText(a.deadline, simToday),
    supplier: "", arrive: "", cost: "", why: a.problem, chips: [], warn: "",
  }));
  const techs = pending.technical.map((t): DecisionItem => {
    const decidable = Boolean(t.issue_id && t.option_id);
    return {
      id: t.issue_id ?? `line|${t.sku}`, issueId: t.issue_id ?? "", optionId: t.option_id ?? "", kind: "tech", readOnly: !decidable, tier: t.tier ?? "",
      icon: t.expected_delivery || t.qty ? "shopping_basket" : "bolt", level: t.tier ? tierLabel(t.tier) : "", title: t.label, summary: "",
      value: benefitText(null), conf: t.confidence ?? 0, confPct: confText(t.confidence), deadline: deadlineText(t.deadline, simToday),
      supplier: t.supplier_name ?? t.supplier_id ?? "", arrive: t.expected_delivery ? `llega ${weekdayDay(t.expected_delivery)}` : "",
      cost: t.cost_usd?.mid ? usd(t.cost_usd.mid) : "", why: t.why, chips: t.impact_chips ?? [], warn: t.warning ?? "",
    };
  });
  return [...techs, ...approvals];
}

export type AnalysisState =
  | { status: "loading" }
  | { status: "soon" }
  | { status: "error"; message: string }
  | { status: "ok"; data: IssueAnalysis };

const sec = (label: string, icon: string, color: string, items: string[]): AnalysisSection => {
  const clean = items.filter(Boolean);
  return { label, icon, color, items: clean.length ? clean : NONE };
};

/** Sections of the analysis (Analizar) or dialogue (Dialogar) card, straight from GET /issues/{id}/analysis (Spanish from the backend). */
export function analysisSections(mode: "analizar" | "dialogo", a: IssueAnalysis): AnalysisSection[] {
  if (mode === "analizar")
    return [
      sec("Problema", "report", "#7a5649", [a.problem]),
      sec("Recomendación", "recommend", "#331b11", [a.recommendation.label]),
      sec("Pros", "add_circle", "#cb9564", a.pros),
      sec("Contras", "remove_circle", "#82746f", a.cons),
      ...(a.requires_approval ? [sec("Requiere tu aprobación", "how_to_reg", "#4b3025", [`${tierLabel(a.tier)}: la decisión es tuya.`])] : []),
    ];
  const alts = a.dialog.alternatives.map((x) => (x.net_usd_mid == null ? x.label : `${x.label} (efecto neto ${usd(x.net_usd_mid)})`));
  return [
    sec("Por qué", "help", "#7a5649", [a.dialog.why]),
    sec("Si aceptas", "check_circle", "#cb9564", [a.dialog.if_accept]),
    sec("Si no actúas", "block", "#82746f", [a.dialog.if_not_act]),
    sec("Alternativas", "alt_route", "#331b11", alts.length ? alts : ["Sin alternativas propuestas por el sistema."]),
  ];
}

/** GET /cases/{id}/issues/{issue_id}/analysis. 404/501 mean "not deployed": the UI says "Disponible pronto". */
export async function fetchIssueAnalysis(api: Api, caseId: string, issueId: string): Promise<AnalysisState> {
  try {
    return { status: "ok", data: await api.getAnalysis(caseId, issueId) };
  } catch (e) {
    if (isUnavailable(e)) return SOON;
    return { status: "error", message: (e as Error).message };
  }
}

/** GET /cases/{id}/outlook?days=2 feeds Hoy and Mañana. A 404/501 means "not deployed yet": the UI says "Disponible pronto". */
export async function fetchOutlook(api: Api, caseId: string): Promise<Source<Outlook>> {
  try {
    return { status: "ok", data: await api.getOutlook(caseId, { days: "2" }) };
  } catch (e) {
    if (isUnavailable(e)) return SOON;
    throw e;
  }
}

// ---------------------------------------------------------------------------------------------
// Sucursal window
// ---------------------------------------------------------------------------------------------
export interface Stat {
  label: string;
  value: string;
  sub: string;
}

export interface DayView {
  title: string;
  date: string;
  expected: string;
  range: string | null;
  /** Same-weekday average, shown when the forecast has no point for the day. */
  baseline: string | null;
  /** "Pronóstico", "Pronóstico cerrado". */
  conf: string;
  real: string;
  realNote: string;
  /** True when real sales are an actual figure (Ayer). */
  realKnown: boolean;
  weather: { icon: string; tag: string; temp: string; text: string; effect: string | null };
  traffic: { value: string; caption: string };
  context: string;
  orders: { label: string; value: string };
  ticket: { value: string };
  conversion: { value: string };
  waste: Stat;
  lost: Stat;
}

export interface DayViewInput {
  asOf: string;
  forecast: ForecastResponse | null;
  /** Day summary of as_of - 1. */
  ayer: DaySummary | null;
  /** Day summary of as_of: only its calendar context is read, never its sales. */
  hoy: DaySummary | null;
  kpis: Kpis | null;
  expiring: ExpiringResponse | null;
  outlook?: Outlook | null;
}

const NO_FORECAST = "Sin pronóstico";
const cap = (t: string): string => t.charAt(0).toUpperCase() + t.slice(1);
const weekdayLong = (iso: string): string => cap(new Intl.DateTimeFormat("es-MX", { weekday: "long", timeZone: "UTC" }).format(new Date(`${iso}T00:00:00Z`)));
const rangeText = (lo?: number | null, hi?: number | null): string | null => (lo == null || hi == null ? null : `${usdWhole(lo)} – ${usdWhole(hi)}`);

function contextText(date: string, s: DaySummary | null): string {
  const c = s?.context;
  return [weekdayLong(date), c?.is_holiday ? c.holiday_name || "Feriado" : "", c?.is_school_break ? "vacaciones escolares" : ""].filter(Boolean).join(" · ");
}

/** True for the honest empty values, which the UI draws small and muted. */
export const isPlaceholder = (v: string): boolean => ["Sin datos", SOON_TEXT, NO_FORECAST, "Pendiente"].includes(v);

export function buildDayView(day: DayKey, input: DayViewInput): DayView {
  const { asOf, forecast, ayer, hoy, kpis, expiring, outlook } = input;
  const date = day === "ayer" ? shiftDate(asOf, -1) : day === "hoy" ? asOf : shiftDate(asOf, 1);
  const point = forecast?.points.find((p) => p.date === date);
  const od: OutlookDay | undefined = day === "ayer" ? undefined : outlook?.days.find((d) => d.date === date);
  const sales = od?.net_sales;
  const expectedValue = sales?.mid ?? point?.forecast;
  const range = sales ? rangeText(sales.low, sales.high) : point ? rangeText(point.p10, point.p90) : null;
  const titles = { ayer: "Así cerró ayer", hoy: "Hoy en la sucursal", manana: "Mañana en la sucursal" } as const;
  const future = day !== "ayer";
  const lostKpi = kpis?.lost_sales_usd;

  const view: DayView = {
    title: titles[day],
    date: cap(longDate(date)),
    expected: expectedValue == null ? "Sin datos" : usd(expectedValue),
    range,
    baseline: null,
    conf: day === "ayer" ? "Pronóstico cerrado" : "Pronóstico",
    real: "Pendiente",
    realNote: day === "hoy" ? "Se registra al cierre" : "Día futuro",
    realKnown: false,
    weather: { icon: "partly_cloudy_day", tag: "pronóstico", temp: NO_FORECAST, text: NO_FORECAST, effect: null },
    traffic: { value: SOON_TEXT, caption: "visitas esperadas" },
    context: contextText(date, day === "manana" ? null : day === "hoy" ? hoy : ayer),
    orders: { label: "Pedidos esperados", value: SOON_TEXT },
    ticket: { value: SOON_TEXT },
    conversion: { value: SOON_TEXT },
    waste: { label: "Merma esperada", value: SOON_TEXT, sub: "a costo" },
    lost: {
      label: "Venta perdida (7 días)",
      value: lostKpi?.mid == null ? "Sin datos" : usd(lostKpi.mid),
      sub: `${rangeText(lostKpi?.low, lostKpi?.high) ?? "Sin datos"} · por falta de producto`,
    },
  };

  const weekdayAvg = (day === "ayer" ? ayer : day === "hoy" ? hoy : null)?.vs_same_weekday_avg;
  if (expectedValue == null && weekdayAvg) view.baseline = `Promedio mismo día (${weekdayAvg.weeks_used} sem): ${usd(weekdayAvg.baseline_net_sales)}`;

  if (!future) {
    const t = ayer?.totals;
    const wx = ayer?.context?.weather;
    const delta = ayer?.vs_same_weekday_avg?.delta_pct;
    const rainy = (wx?.precip_mm ?? 0) > 0;
    view.real = t?.net_sales == null ? "Sin datos" : usd(t.net_sales);
    view.realKnown = t?.net_sales != null;
    view.realNote = delta == null ? "Sin comparativo" : `${signedPct(delta)} vs promedio mismo día`;
    view.weather = {
      icon: rainy ? "rainy" : "sunny",
      tag: "observado",
      temp: wx?.temp_max_c == null || wx.temp_min_c == null ? "Sin datos" : `${Math.round(wx.temp_max_c)}° / ${Math.round(wx.temp_min_c)}°`,
      text: wx ? (rainy ? `Lluvia ${wx.precip_mm} mm` : "Sin lluvia") : "Sin datos",
      effect: null,
    };
    view.traffic = { value: t?.footfall == null ? "Sin datos" : String(Math.round(t.footfall)), caption: "visitas" };
    view.orders = { label: "Pedidos", value: t?.transactions == null ? "Sin datos" : String(t.transactions) };
    view.ticket = { value: t ? avgTicket(t.net_sales, t.transactions) : "Sin datos" };
    view.conversion = { value: t?.footfall && t.transactions != null ? `${((t.transactions / t.footfall) * 100).toFixed(1)}%` : "Sin datos" };
    view.waste = { label: "Merma real", value: "Sin datos", sub: kpis?.waste_usd == null ? "Sin datos" : `Últimos 7 días: ${usd(kpis.waste_usd)}` };
    return view;
  }

  if (od) {
    if (od.transactions?.mid != null) view.orders.value = String(Math.round(od.transactions.mid));
    if (od.avg_ticket?.mid != null) view.ticket.value = usd(od.avg_ticket.mid);
    const waste: Range3 | null | undefined = od.expected_waste_usd;
    if (waste?.mid != null) view.waste = { label: "Merma esperada", value: usd(waste.mid), sub: `a costo · ${rangeText(waste.low, waste.high) ?? "Sin datos"}` };
    const lost = od.expected_lost_sales_usd;
    if (lost?.mid != null) view.lost = { label: "Venta perdida esperada", value: usd(lost.mid), sub: `${rangeText(lost.low, lost.high) ?? "Sin datos"} · por falta de producto` };
  }
  const exp = expiring?.by_day?.find((d) => d.date === date)?.waste_usd;
  if (view.waste.value === SOON_TEXT && exp?.mid != null) view.waste = { label: "Merma esperada", value: usd(exp.mid), sub: `a costo · ${rangeText(exp.low, exp.high) ?? "Sin datos"}` };
  return view;
}

export interface InventoryRow {
  sku: string;
  name: string;
  now: string;
  out: string;
  buy: string;
  cover: string;
  /** 0..100, current stock against the daily outflow. */
  fill: number;
}

const num = (n: number): string => String(Math.round(n * 100) / 100);

export function buildInventoryRows(inv: InventoryResponse | null, plan: OrderPlan | null, limit = 6): InventoryRow[] {
  return (inv?.items ?? []).slice(0, limit).map((it) => {
    const line = plan?.lines.find((l) => l.sku === it.sku);
    const denom = Math.max(it.avg_daily_demand, it.on_hand);
    return {
      sku: it.sku,
      name: it.product_name,
      now: num(it.on_hand),
      out: `${num(it.avg_daily_demand)} /día`,
      buy: line?.qty ? `+${line.qty}${line.expected_delivery ? ` · llega ${weekdayDay(line.expected_delivery)}` : ""}` : "—",
      cover: it.days_of_cover == null ? "Sin datos" : `${num(it.days_of_cover)} días de cobertura`,
      fill: denom > 0 ? Math.min(100, Math.round((it.on_hand / denom) * 100)) : 0,
    };
  });
}

export interface ScheduledRow {
  what: string;
  who: string;
  when: string;
  status: string;
  tone: "ok" | "warn";
}

/** Placed purchase orders on the way: late ones first, then the soonest expected. */
export function buildScheduled(d: DeliveriesResponse | null, limit = 4): ScheduledRow[] {
  const rows = (d?.days ?? [])
    .flatMap((day) => day.deliveries)
    .filter((x) => x.kind === "open_po" && (x.status === "late" || x.status === "expected"))
    .sort((a, b) => Number(b.status === "late") - Number(a.status === "late") || a.expected_date.localeCompare(b.expected_date));
  return rows.slice(0, limit).map((x) => {
    const l = x.lines[0];
    return {
      what: l ? `${l.product_name} · ${l.qty}` : x.po_id,
      who: x.supplier_name,
      when: weekdayDay(x.expected_date),
      status: x.status === "late" ? "Atrasado" : "Colocado",
      tone: x.status === "late" ? "warn" : "ok",
    };
  });
}

// ---------------------------------------------------------------------------------------------
// Memorias: decision_log (GET /history) + supplier performance + rejections learned in this session.
// GET /cases/{id}/memories (pending) will replace all of it behind `fetchMemories`.
// ---------------------------------------------------------------------------------------------
const ACTION_LABELS: Record<string, string> = {
  place_order: "Compra",
  skip_order: "Omitir pedido",
  adjust_order_qty: "Ajustar pedido",
  markdown_end_of_day: "Descuento al cierre",
  transfer: "Transferencia",
};
const actionLabel = (a: string): string => ACTION_LABELS[a] ?? a;
const skuOf = (d: DecisionLogEntry): string => d.sku || d.issue_id.split("|")[2] || d.issue_id;

function decisionMemory(d: DecisionLogEntry): Memory | null {
  const date = dayMonth(d.created_at);
  if (d.status === "rejected") {
    return {
      id: `dec-${d.decision_id}`, cat: "preferencias", icon: "person", tag: "Motivo de rechazo",
      text: d.reason ? `«${d.reason}»` : "Rechazada sin motivo", src: `Rechazo · ${actionLabel(d.action_type)} · ${skuOf(d)}`, conf: date,
    };
  }
  if (d.status === "approved") {
    return {
      id: `dec-${d.decision_id}`, cat: d.kind === "calendar_uplift" ? "eventos" : "demanda", icon: d.kind === "calendar_uplift" ? "celebration" : "bakery_dining",
      tag: "Decisión aprobada", text: `Aprobaste: ${actionLabel(d.action_type)} de ${skuOf(d)}.`, src: `Registro de decisiones · ${d.tier ?? ""}`.trim(), conf: date,
    };
  }
  return null;
}

function supplierMemory(s: SupplierPerformance): Memory {
  return {
    id: `sup-${s.supplier_id}`, cat: "proveedores", icon: "local_shipping", tag: "Proveedor",
    text: `${s.supplier_name}: ${s.on_time_pct}% a tiempo, entrega real de ${s.lead_time_mean_days} días y surte el ${s.fill_pct}%.`,
    src: `Desempeño de proveedores · ${s.window_days} días`, conf: `${s.received_pos} pedidos`,
  };
}

export function buildMemories(input: { history: HistoryResponse | null; suppliers: SupplierPerformance[] | null; learned: Memory[] }): Memory[] {
  const decisions = [...(input.history?.decision_log ?? [])]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .map(decisionMemory)
    .filter((m): m is Memory => m !== null)
    .slice(0, 30);
  return [...input.learned, ...decisions, ...(input.suppliers ?? []).map(supplierMemory)];
}

export function filterMemories(list: Memory[], cat: string, query: string): Memory[] {
  const q = query.trim().toLowerCase();
  return list.filter((m) => (cat === "todas" || m.cat === cat) && (!q || `${m.tag} ${m.text} ${m.src}`.toLowerCase().includes(q)));
}

// ---------------------------------------------------------------------------------------------
// Advertencias: open alerts (GET /alerts) + integrity issues (GET /issues?category=integrity).
// ---------------------------------------------------------------------------------------------
export type WarningCategory = "operacion" | "datos" | "auto";

export interface WarningItem {
  id: string;
  cat: WarningCategory;
  tone: "warn" | "info";
  toneLabel: string;
  icon: string;
  title: string;
  body: string;
  /** Agent that raised it; null until `agent_id` is served. */
  agent: string | null;
  time: string;
  /** Only N1 automatic actions can be reverted, and N1 auto-execution does not exist. */
  revertible: boolean;
}

function alertCopy(a: AlertRecord): { icon: string; title: string; body: string } {
  const i = a.issue ?? {};
  const sev = a.severity_usd != null ? usd(a.severity_usd) : null;
  switch (i.kind) {
    case "overstock_waste":
      return { icon: "hourglass_bottom", title: `Exceso de inventario: ${i.product_name || i.sku || "producto"}`, body: sev ? `Merma estimada de ${sev}.` : "Sin datos" };
    case "calendar_uplift":
      return { icon: "event", title: `Efecto de calendario: ${i.event?.name ?? "evento"}`, body: sev ? `Impacto estimado de ${sev} si el plan no lo refleja.` : "Sin datos" };
    case "compliance_deviation":
      return { icon: "rule", title: "Acción aprobada sin ejecutar", body: "Una decisión aprobada no se ejecutó. Revisa qué pasó." };
    default:
      return { icon: "warning", title: i.kind ?? "Advertencia", body: sev ? `Impacto estimado de ${sev}.` : "Sin datos" };
  }
}

const INTEGRITY_TITLES: Record<string, string> = {
  orphan_sku: "Ventas sin producto en el catálogo",
  sku_key_mismatch: "Claves de producto que no coinciden",
};

export function buildWarnings(input: { alerts: AlertRecord[]; integrity: Issue[] }): WarningItem[] {
  const ops = input.alerts
    .filter((a) => a.state === "nueva")
    .map((a): WarningItem => ({
      id: a.alert_id, cat: "operacion", tone: "warn", toneLabel: "Seguimiento", ...alertCopy(a),
      agent: alertAgent(a), time: a.as_of ? dayMonth(a.as_of) : "", revertible: false,
    }));
  const data = input.integrity.map((i): WarningItem => ({
    id: i.issue_id, cat: "datos", tone: "info", toneLabel: "Datos", icon: "sensors",
    title: INTEGRITY_TITLES[i.kind] ?? i.kind, body: i.exposure_usd != null ? `Exposición de ${usd(i.exposure_usd)}.` : "Sin datos",
    agent: null, time: i.as_of ? dayMonth(i.as_of) : "", revertible: false,
  }));
  return [...ops, ...data];
}

export const filterWarnings = (list: WarningItem[], cat: string): WarningItem[] => list.filter((w) => cat === "todas" || w.cat === cat);
