import { isUnavailable, type Api } from "../api";
import { avgTicket, clockTime, dayMonth, longDate, shiftDate, signedPct, usd, usdWhole, weekdayDay } from "../format";
import type {
  AgentStatus, AlertRecord, DaySummary, DeliveriesResponse, ExpiringResponse, ForecastResponse, InventoryResponse, Issue, IssueAnalysis, OrderPlan,
  Outlook, OutlookDay, MemoryRecord, PendingResponse, Range3, TurnProgress,
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
  /** Issue the chat is pinned to (sent as the message `context`); absent for warnings, which are not issues. */
  issueId?: string;
  optionId?: string;
}

// ---------------------------------------------------------------------------------------------
// Data sources. Each source is ONE function so swapping it for the real route is a one-line change.
// `{status: "soon"}` means the backend route does not exist yet: the UI shows "Disponible pronto".
// See the GAP LIST in odd/tasks/copiloto.md for the suggested contracts.
// ---------------------------------------------------------------------------------------------

export type Source<T> = { status: "ok"; data: T } | { status: "soon" };
const SOON = { status: "soon" } as const;
export const SOON_TEXT = "Disponible pronto";

/** GET /cases/{id}/autonomy/log (pending). */
export const fetchAutonomyLog = async (_api: Api, _caseId: string): Promise<Source<never>> => SOON;
/** POST /cases/{id}/autonomy/{action_id}/revert (pending). */
export const revertAutonomy = async (_api: Api, _caseId: string, _actionId: string): Promise<Source<never>> => SOON;

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
  /** "Confianza calibrada" or "Confianza estimada (sin calibrar)". */
  confLabel: string;
  deadline: string;
  supplier: string;
  arrive: string;
  cost: string;
  why: string;
  /** Backend impact chips (technical cards). */
  chips: string[];
  warn: string;
  /** Spanish labels of every kind merged into this issue (approvals). */
  kinds?: string[];
  /** A stock transfer between stores (kind transfer_opportunity / action transfer_stock). */
  isTransfer?: boolean;
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
  transfer_stock: "swap_horiz",
};

function benefitText(r: Range3 | null | undefined): string {
  if (!r) return "";
  const { low, mid, high } = r;
  if (low != null && high != null && low !== high) return `+${usd(low)} a ${usd(high)}`;
  const one = mid ?? low ?? high;
  return one ? `+${usd(one)}` : "";
}

/** Technical confidence: a bare number (old) or {score, calibrated} (Wave 15). */
const confScore = (c: PendingResponse["technical"][number]["confidence"] | undefined): number | null => (c == null ? null : typeof c === "number" ? c : (c.score ?? null));

const confText = (score: number | null | undefined): string => (score == null ? "Sin datos" : pct(score));

/** "Calibrada" only when the backend says the score is calibrated; a bare number (old backend) is not. */
export const confLabelFor = (calibrated: boolean | undefined): string => (calibrated ? "Confianza calibrada" : "Confianza estimada (sin calibrar)");
const confCalibrated = (c: PendingResponse["technical"][number]["confidence"] | undefined): boolean => (c != null && typeof c === "object" ? c.calibrated === true : false);

/** Maps GET /decisions/pending to cards. Approvals and technical come split by the backend; a technical line with no issue/option is read-only. */
export function buildPendingItems(pending: PendingResponse | null, simToday: string): DecisionItem[] {
  if (!pending) return [];
  const approvals = pending.approvals.map((a): DecisionItem => ({
    id: a.issue_id, issueId: a.issue_id, optionId: a.recommendation.option_id, kind: "approval", readOnly: false, tier: a.tier,
    icon: ACTION_ICONS[a.recommendation.action_type] ?? "bolt", level: tierLabel(a.tier), title: a.recommendation.label, summary: a.problem,
    value: benefitText(a.impact_usd), conf: a.confidence.score ?? 0, confPct: confText(a.confidence.score), confLabel: confLabelFor(a.confidence.calibrated), deadline: deadlineText(a.deadline, simToday),
    supplier: "", arrive: "", cost: "", why: a.problem, chips: [], warn: "",
    kinds: (a.kinds ?? []).map((k) => kindLabelEs(k)),
    isTransfer: a.kind === "transfer_opportunity" || a.recommendation.action_type === "transfer_stock",
  }));
  const techs = pending.technical.map((t): DecisionItem => {
    const decidable = Boolean(t.issue_id && t.option_id);
    return {
      id: t.issue_id ?? `line|${t.sku}`, issueId: t.issue_id ?? "", optionId: t.option_id ?? "", kind: "tech", readOnly: !decidable, tier: t.tier ?? "",
      icon: t.expected_delivery || t.qty ? "shopping_basket" : "bolt", level: t.tier ? tierLabel(t.tier) : "", title: t.label, summary: "",
      value: benefitText(null), conf: confScore(t.confidence) ?? 0, confPct: confText(confScore(t.confidence)), confLabel: confLabelFor(confCalibrated(t.confidence)), deadline: deadlineText(t.deadline, simToday),
      supplier: t.supplier_name ?? t.supplier_id ?? "", arrive: t.expected_delivery ? `llega ${weekdayDay(t.expected_delivery)}` : "",
      cost: t.cost_usd?.mid ? usd(t.cost_usd.mid) : "", why: t.why, chips: t.impact_chips ?? [], warn: t.warning ?? "",
    };
  });
  // The same issue can come back as an approval and as a technical line (or merged under several kinds): one card per issue_id,
  // and the approval wins because it asks for the manager's opinion.
  const approvalIds = new Set(approvals.map((a) => a.id));
  const mergedIds = new Set(pending.approvals.flatMap((a) => a.merged_issue_ids ?? []));
  const seen = new Set<string>();
  const uniqueTechs = techs.filter((t) => {
    if (approvalIds.has(t.id) || mergedIds.has(t.id) || seen.has(t.id)) return false;
    seen.add(t.id);
    return true;
  });
  const uniqueApprovals = approvals.filter((a, i) => approvals.findIndex((x) => x.id === a.id) === i && !mergedIds.has(a.id));
  return [...uniqueTechs, ...uniqueApprovals];
}

/** "Consultando a A y B…" from the turn progress; null when nobody is being consulted. */
export function consultingText(progress: readonly TurnProgress[]): string | null {
  const names = progress.filter((p) => p.state === "consulting").map((p) => p.display_name_es);
  if (names.length === 0) return null;
  const list = names.length === 1 ? names[0] : `${names.slice(0, -1).join(", ")} y ${names[names.length - 1]}`;
  return `Consultando a ${list}…`;
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
  expiring: ExpiringResponse | null;
  /** GET /outlook: null/undefined = route unavailable ("Disponible pronto"); an object without the day = "Sin datos". */
  outlook?: Outlook | null;
  /** GET /forecast?metric=...: same convention as `outlook`. */
  metrics?: MetricForecasts | null;
}

export const METRICS = ["footfall", "transactions", "avg_ticket", "conversion"] as const;
export type Metric = (typeof METRICS)[number];
export type MetricForecasts = Partial<Record<Metric, ForecastResponse | null>>;

/** GET /cases/{id}/forecast?metric=... for each metric (store level). 404/501 on every metric means "not deployed". */
export async function fetchMetricForecasts(api: Api, caseId: string, asOf: string): Promise<Source<MetricForecasts>> {
  const results = await Promise.allSettled(METRICS.map((metric) => api.getForecast(caseId, { metric, from: shiftDate(asOf, -1), to: shiftDate(asOf, 1), level: "store" })));
  const out: MetricForecasts = {};
  let served = 0;
  results.forEach((r, i) => {
    out[METRICS[i]] = r.status === "fulfilled" ? r.value : null;
    if (r.status === "fulfilled") served++;
    else if (!isUnavailable(r.reason)) served++; // a failure other than "not deployed" is still a deployed route
  });
  return served === 0 ? SOON : { status: "ok", data: out };
}

const NO_FORECAST = "Sin pronóstico";
const NO_DATA = "Sin datos";
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
  const { asOf, forecast, ayer, hoy, expiring, outlook, metrics } = input;
  const date = day === "ayer" ? shiftDate(asOf, -1) : day === "hoy" ? asOf : shiftDate(asOf, 1);
  const point = forecast?.points.find((p) => p.date === date);
  const od: OutlookDay | undefined = outlook?.days.find((d) => d.date === date);
  const sales = od?.net_sales;
  const expectedValue = sales?.mid ?? point?.forecast;
  const range = sales ? rangeText(sales.low, sales.high) : point ? rangeText(point.p10, point.p90) : null;
  const titles = { ayer: "Así cerró ayer", hoy: "Hoy en la sucursal", manana: "Mañana en la sucursal" } as const;
  const future = day !== "ayer";

  const view: DayView = {
    title: titles[day],
    date: cap(longDate(date)),
    expected: expectedValue == null ? "Sin datos" : usd(expectedValue),
    range,
    conf: day === "ayer" ? (od?.vs_forecast_pct != null ? `${signedPct(od.vs_forecast_pct)} vs pronóstico` : "Pronóstico cerrado") : `Pronóstico ${NO_DATA}`,
    real: "Pendiente",
    realNote: day === "hoy" ? "Se registra al cierre" : "Día futuro",
    realKnown: false,
    weather: { icon: "partly_cloudy_day", tag: "pronóstico", temp: NO_FORECAST, text: NO_FORECAST, effect: NO_DATA },
    traffic: { value: metrics ? NO_DATA : SOON_TEXT, caption: "visitas esperadas" },
    context: contextText(date, day === "manana" ? null : day === "hoy" ? hoy : ayer),
    orders: { label: "Pedidos esperados", value: metrics || outlook ? NO_DATA : SOON_TEXT },
    ticket: { value: metrics || outlook ? NO_DATA : SOON_TEXT },
    conversion: { value: metrics ? NO_DATA : SOON_TEXT },
    waste: { label: "Merma esperada", value: outlook ? NO_DATA : SOON_TEXT, sub: "a costo" },
    lost: { label: "Venta perdida esperada", value: outlook ? NO_DATA : SOON_TEXT, sub: "por falta de producto" },
  };

  if (!future) {
    const t = ayer?.totals;
    const wx = ayer?.context?.weather;
    const delta = ayer?.vs_same_weekday_avg?.delta_pct;
    const rainy = (wx?.precip_mm ?? 0) > 0;
    // Yesterday's real sales: the day summary, else the outlook's backtest actual.
    const realSales = t?.net_sales ?? od?.actual?.net_sales;
    view.real = realSales == null ? "Sin datos" : usd(realSales);
    view.realKnown = realSales != null;
    view.realNote = delta == null ? "Sin comparativo" : `${signedPct(delta)} vs promedio mismo día`;
    view.weather = {
      icon: rainy ? "rainy" : "sunny",
      tag: "observado",
      temp: wx?.temp_max_c == null || wx.temp_min_c == null ? "Sin datos" : `${Math.round(wx.temp_max_c)}° / ${Math.round(wx.temp_min_c)}°`,
      text: wx ? (rainy ? `Lluvia ${wx.precip_mm} mm` : "Sin lluvia") : "Sin datos",
      effect: NO_DATA,
    };
    view.traffic = { value: t?.footfall == null ? "Sin datos" : String(Math.round(t.footfall)), caption: "visitas esperadas" };
    view.orders = { label: "Pedidos esperados", value: t?.transactions == null ? "Sin datos" : String(t.transactions) };
    view.ticket = { value: t ? avgTicket(t.net_sales, t.transactions) : "Sin datos" };
    view.conversion = { value: t?.footfall && t.transactions != null ? `${((t.transactions / t.footfall) * 100).toFixed(1)}%` : "Sin datos" };
    view.waste = { label: "Merma esperada", value: "Sin datos", sub: "a costo · real" };
    return view;
  }

  const metricPoint = (m: Metric) => metrics?.[m]?.points.find((p) => p.date === date);
  const visits = metricPoint("footfall");
  if (visits) view.traffic.value = String(Math.round(visits.forecast));
  const txPoint = metricPoint("transactions");
  if (txPoint) view.orders.value = String(Math.round(txPoint.forecast));
  const ticketPoint = metricPoint("avg_ticket");
  if (ticketPoint) view.ticket.value = usd(ticketPoint.forecast);
  const convPoint = metrics?.conversion?.conversion_valid === false ? undefined : metricPoint("conversion");
  if (convPoint) view.conversion.value = `${(convPoint.forecast * 100).toFixed(1)}%`;
  if (od) {
    if (od.transactions?.mid != null) view.orders.value = String(Math.round(od.transactions.mid));
    if (od.avg_ticket?.mid != null) view.ticket.value = usd(od.avg_ticket.mid);
    const waste: Range3 | null | undefined = od.expected_waste_usd;
    if (waste?.mid != null) view.waste = { label: "Merma esperada", value: usd(waste.mid), sub: `a costo · ${rangeText(waste.low, waste.high) ?? "Sin datos"}` };
    const lost = od.expected_lost_sales_usd;
    if (od.weather_note) view.weather = { ...view.weather, temp: od.weather_note, text: od.weather_note };
    if (lost && rangeText(lost.low, lost.high)) view.lost = { label: "Venta perdida esperada", value: rangeText(lost.low, lost.high)!, sub: "por falta de producto" };
  }
  const exp = expiring?.by_day?.find((d) => d.date === date)?.waste_usd;
  if ((view.waste.value === SOON_TEXT || view.waste.value === NO_DATA) && exp?.mid != null) view.waste = { label: "Merma esperada", value: usd(exp.mid), sub: `a costo · ${rangeText(exp.low, exp.high) ?? "Sin datos"}` };
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
  /** Backend status; null when the inventory does not serve it. */
  status: "critical" | "watch" | "ok" | null;
  statusLabel: string;
  /** Backend explanation of the status. */
  reason: string;
  /** Backend closing sentence (display_status_es); empty when the inventory does not serve it. */
  display: string;
}

const num = (n: number): string => String(Math.round(n * 100) / 100);
const STATUS_LABELS = { critical: "Crítico", watch: "Seguimiento", ok: "En orden" } as const;

export function buildInventoryRows(inv: InventoryResponse | null, plan: OrderPlan | null, limit = Infinity): InventoryRow[] {
  return (inv?.items ?? []).slice(0, limit).map((it) => {
    const line = plan?.lines.find((l) => l.sku === it.sku);
    const denom = Math.max(it.avg_daily_demand, it.on_hand);
    const out = it.forecast_outflow_units != null ? `${num(it.forecast_outflow_units)} en ${inv?.outflow_days ?? 3} días` : `${num(it.avg_daily_demand)} /día`;
    const buy =
      it.scheduled_in_units != null
        ? it.scheduled_in_units > 0
          ? `+${num(it.scheduled_in_units)}${it.next_delivery_date ? ` · llega ${weekdayDay(it.next_delivery_date)}` : ""}`
          : "—"
        : line?.qty
          ? `+${line.qty}${line.expected_delivery ? ` · llega ${weekdayDay(line.expected_delivery)}` : ""}`
          : "—";
    return {
      sku: it.sku,
      name: it.product_name,
      now: num(it.on_hand),
      out,
      buy,
      cover: it.days_of_cover == null ? "Sin datos" : `${num(it.days_of_cover)} días de cobertura`,
      fill: denom > 0 ? Math.min(100, Math.round((it.on_hand / denom) * 100)) : 0,
      status: it.status ?? null,
      statusLabel: it.status ? STATUS_LABELS[it.status] : "",
      reason: it.status_reason ?? "",
      display: it.display_status_es ?? "",
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
// Memorias: GET /cases/{id}/memories (decision log, rejection reasons and the store's experiences, newest first).
// ---------------------------------------------------------------------------------------------
const MEMORY_META: Record<string, { icon: string; tag: string }> = {
  proveedores: { icon: "local_shipping", tag: "Proveedor" },
  demanda: { icon: "bakery_dining", tag: "Demanda" },
  eventos: { icon: "celebration", tag: "Evento" },
  preferencias: { icon: "person", tag: "Preferencia del gerente" },
};
const MEMORY_SOURCES: Record<string, string> = {
  decision_log: "Registro de decisiones",
  rejection_reason: "Motivo de rechazo",
  backboard: "Experiencia de la sucursal",
};

export function buildMemories(records: readonly MemoryRecord[] | null): Memory[] {
  return (records ?? []).map((r): Memory => {
    const meta = MEMORY_META[r.category] ?? { icon: "psychology", tag: r.category };
    return {
      id: r.memory_id,
      cat: r.category as MemoryCategory,
      icon: meta.icon,
      tag: meta.tag,
      text: r.text,
      src: `${MEMORY_SOURCES[r.source] ?? r.source} · ${dayMonth(r.created_at)}`,
      conf: `${r.cases_count} ${r.cases_count === 1 ? "caso" : "casos"} · ${r.verified ? "verificada" : "sin verificar"}`,
      ...(r.new ? { isNew: true } : {}),
    };
  });
}

/** GET /cases/{id}/memories. 404/501 mean "not deployed": the UI says "Disponible pronto". */
export async function fetchMemories(api: Api, caseId: string): Promise<Source<MemoryRecord[]>> {
  try {
    return { status: "ok", data: await api.getMemories(caseId) };
  } catch (e) {
    if (isUnavailable(e)) return SOON;
    throw e;
  }
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
  tone: "warn" | "info" | "auto";
  toneLabel: string;
  icon: string;
  title: string;
  body: string;
  /** Spanish name of the agent that raised it; null when unknown. */
  agent: string | null;
  time: string;
  /** Only N1 automatic actions can be reverted, and N1 auto-execution does not exist. */
  revertible: boolean;
}

/** Spanish names for issue kinds, used when the backend sends no kind_label_es. Raw kinds are never shown. */
const KIND_LABELS_ES: Record<string, string> = {
  stockout_risk: "Riesgo de desabasto",
  overstock_waste: "Sobreinventario y merma",
  calendar_uplift: "Efecto de calendario",
  compliance_deviation: "Acción aprobada sin ejecutar",
  orphan_sku: "Ventas sin producto en el catálogo",
  sku_key_mismatch: "Claves de producto que no coinciden",
  inflated_order: "Pedido inflado",
  expiring: "Próximo a caducar",
  transfer_opportunity: "Oportunidad de traslado",
};
export const kindLabelEs = (kind: string | null | undefined, label?: string | null): string => label || (kind ? KIND_LABELS_ES[kind] : undefined) || "Advertencia";

function alertCopy(a: AlertRecord): { icon: string; title: string; body: string } {
  const copy = alertCopyBase(a);
  return { ...copy, title: a.title_es || copy.title };
}

function alertCopyBase(a: AlertRecord): { icon: string; title: string; body: string } {
  const i = a.issue ?? {};
  const sev = a.severity_usd != null ? usd(a.severity_usd) : null;
  switch (i.kind) {
    case "overstock_waste":
      return { icon: "hourglass_bottom", title: `Exceso de inventario: ${i.product_name || i.sku || "producto"}`, body: sev ? `Merma estimada de ${sev}.` : "Sin datos" };
    case "calendar_uplift":
      return { icon: "event", title: `Efecto de calendario: ${i.event?.name ?? "evento"}`, body: sev ? `Impacto estimado de ${sev} si el plan no lo refleja.` : "Sin datos" };
    case "compliance_deviation":
      return { icon: "rule", title: "Acción aprobada sin ejecutar", body: "Una decisión aprobada no se ejecutó. Revisa qué pasó." };
    case "transfer_opportunity":
      return { icon: "swap_horiz", title: kindLabelEs(i.kind, a.kind_label_es), body: sev ? `Trasladar stock puede ahorrar ${sev}.` : "Hay stock que se puede trasladar a otra sucursal." };
    default:
      return { icon: "warning", title: kindLabelEs(i.kind, a.kind_label_es), body: sev ? `Impacto estimado de ${sev}.` : "Sin datos" };
  }
}

const INTEGRITY_TITLES: Record<string, string> = {
  orphan_sku: "Ventas sin producto en el catálogo",
  sku_key_mismatch: "Claves de producto que no coinciden",
};

const ALERT_CATEGORIES: Record<string, { cat: WarningCategory; tone: WarningItem["tone"]; toneLabel: string }> = {
  operacion: { cat: "operacion", tone: "warn", toneLabel: "Seguimiento" },
  integridad: { cat: "datos", tone: "info", toneLabel: "Datos" },
  automatica: { cat: "auto", tone: "auto", toneLabel: "Automática" },
};

export function buildWarnings(input: { alerts: AlertRecord[]; integrity: Issue[]; agents?: readonly AgentStatus[] | null }): WarningItem[] {
  const names = new Map((input.agents ?? []).map((a) => [a.agent_id, a.display_name_es]));
  const ops = input.alerts
    .filter((a) => a.state === "nueva")
    .map((a): WarningItem => ({
      id: a.alert_id, ...(ALERT_CATEGORIES[a.category ?? "operacion"] ?? ALERT_CATEGORIES.operacion), ...alertCopy(a),
      agent: (a.agent_id && names.get(a.agent_id)) || null, time: clockTime(a.ts ?? a.created_at) || (a.as_of ? dayMonth(a.as_of) : ""), revertible: false,
    }));
  const data = input.integrity.map((i): WarningItem => ({
    id: i.issue_id, cat: "datos", tone: "info", toneLabel: "Datos", icon: "sensors",
    title: INTEGRITY_TITLES[i.kind] ?? kindLabelEs(i.kind), body: i.exposure_usd != null ? `Exposición de ${usd(i.exposure_usd)}.` : "Sin datos",
    agent: null, time: i.as_of ? dayMonth(i.as_of) : "", revertible: false,
  }));
  return [...ops, ...data];
}

export const filterWarnings = (list: WarningItem[], cat: string): WarningItem[] => list.filter((w) => cat === "todas" || w.cat === cat);
