import { SOON_TEXT, type DecisionItem } from "../../data/copilot";
import { dateLabel } from "../../format";
import ApprovalCard from "./ApprovalCard";
import { DecisionsSkeleton } from "./Skeleton";
import TechDecisionCard from "./TechDecisionCard";

function SectionHead({ title, hint, count, dark }: { title: string; hint: string; count: number; dark?: boolean }) {
  return (
    <div className="flex items-center justify-between px-1">
      <div>
        <h2 className="m-0 font-headline-sm text-headline-sm text-primary">{title}</h2>
        <p className="m-0 font-label-sm text-label-sm font-normal text-on-surface-variant">{hint}</p>
      </div>
      <span className={`rounded-full px-2.5 py-0.5 font-label-md text-label-md ${dark ? "bg-primary-container text-surface" : "bg-surface-container text-secondary"}`}>{count}</span>
    </div>
  );
}

/** Decisiones window: approvals to analyze and technical decisions ready to accept. */
export default function DecisionsWindow({
  items,
  simToday,
  loadState = "ok",
  loading = false,
  menuFor,
  busyId,
  accepted,
  onAnalyze,
  onAccept,
  onReject,
  onToggleMenu,
  onDialog,
}: {
  items: DecisionItem[];
  simToday: string;
  /** "soon": the route answers 404/501; "error": it failed and there is nothing to show. */
  loadState?: "ok" | "soon" | "error";
  /** The decisions are still being fetched: show placeholders, never an empty verdict. */
  loading?: boolean;
  menuFor: string | null;
  busyId: string | null;
  accepted: number;
  onAnalyze: (i: DecisionItem) => void;
  onAccept: (i: DecisionItem) => void;
  onReject: (i: DecisionItem) => void;
  onToggleMenu: (i: DecisionItem) => void;
  onDialog: (i: DecisionItem) => void;
}) {
  const approvals = items.filter((i) => i.kind === "approval");
  const techs = items.filter((i) => i.kind === "tech");
  return (
    <main className="mx-auto flex w-full max-w-[640px] flex-col gap-6 px-4 pb-28 pt-[calc(var(--copilot-header-h,104px)_+_16px)]">
      <header className="flex flex-col gap-1 pt-3">
        <span className="font-label-md text-label-md uppercase tracking-[0.05em] text-on-tertiary-container first-letter:uppercase">{simToday ? dateLabel(simToday) : loading ? "\u00a0" : "Sin datos"}</span>
        <h1 className="m-0 font-headline-lg text-headline-lg tracking-tight text-primary">Decisiones de hoy</h1>
        <p className="m-0 font-body-md text-body-md text-on-surface-variant">El código calcula; el copiloto explica. Tú decides.</p>
      </header>

      {loading && <DecisionsSkeleton />}
      {!loading && loadState !== "ok" && (
        <p role="alert" className="m-0 rounded-[18px] bg-surface-container p-4 text-center text-[13px] leading-[19px] text-on-surface-variant">
          {loadState === "soon" ? `${SOON_TEXT}: las decisiones aún no están disponibles.` : "No se pudieron cargar las decisiones. Se reintentará en un minuto."}
        </p>
      )}

      {!loading && <section className="flex flex-col gap-2">
        <SectionHead title="Se necesita aprobación / opinión" hint="Casos difíciles: analízalos con el copiloto" count={approvals.length} dark />
        {approvals.map((a) => <ApprovalCard key={a.id} item={a} onAnalyze={onAnalyze} />)}
        {approvals.length === 0 && loadState === "ok" && <p className="m-0 rounded-[18px] bg-surface-container p-4 text-center text-[13px] leading-[19px] text-on-surface-variant">Nada pendiente de tu opinión por ahora.</p>}
      </section>}

      {!loading && <section className="flex flex-col gap-2">
        <SectionHead title="Decisiones técnicas" hint="Listas para aceptar · cantidades y fechas calculadas" count={techs.length} />
        {techs.map((t) => (
          <TechDecisionCard key={t.id} item={t} menuOpen={menuFor === t.id} busy={busyId === t.id} onAccept={onAccept} onReject={onReject} onToggleMenu={onToggleMenu} onDialog={onDialog} />
        ))}
        {techs.length === 0 && loadState === "ok" && <p className="m-0 rounded-[18px] bg-surface-container p-4 text-center text-[13px] leading-[19px] text-on-surface-variant">Todas las decisiones técnicas de hoy están resueltas.</p>}
        <p className="m-0 mt-1 flex items-center justify-center gap-1.5 font-label-sm text-label-sm font-normal text-on-surface-variant">
          <span aria-hidden="true" className="material-symbols-outlined text-[14px]">bolt</span>
          0 decisiones automáticas (N1) ya colocadas hoy{accepted > 0 ? ` · ${accepted} aceptada${accepted > 1 ? "s" : ""} por ti` : ""}
        </p>
      </section>}
    </main>
  );
}
