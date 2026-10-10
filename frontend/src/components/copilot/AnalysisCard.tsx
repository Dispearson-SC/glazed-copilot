import { analysisSections, SOON_TEXT, type AnalysisState, type DecisionItem } from "../../data/copilot";

/** Espresso-header card with the analysis (approvals) or the dialogue (technical decisions) of one decision. */
export default function AnalysisCard({
  item,
  analysis,
  mode,
  open,
  busy = false,
  onApprove,
  onReject,
}: {
  item: DecisionItem;
  /** The backend analysis of the issue (GET /issues/{id}/analysis). */
  analysis: AnalysisState;
  mode: "analizar" | "dialogo";
  /** True while the decision is still pending. */
  open: boolean;
  /** A request for this decision is in flight. */
  busy?: boolean;
  onApprove: (item: DecisionItem) => void;
  onReject: (item: DecisionItem) => void;
}) {
  const isAnalysis = mode === "analizar";
  const sections = analysis.status === "ok" ? analysisSections(mode, analysis.data) : [];
  return (
    <article className="overflow-hidden rounded-[18px] border border-partition/60 bg-white shadow-card">
      <div className="flex flex-col gap-1.5 bg-primary-container p-4 text-white">
        <div className="flex items-center gap-1.5">
          <span className="inline-flex items-center gap-1 rounded-full bg-white/[.12] px-2 py-0.5 font-label-sm text-label-sm font-semibold text-tertiary-fixed-dim">
            <span aria-hidden="true" className="material-symbols-outlined text-[14px]">{isAnalysis ? "query_stats" : "forum"}</span>
            {isAnalysis ? "Análisis" : "Diálogo"}
          </span>
          {item.level && <span className="rounded-full bg-on-tertiary-container px-2 py-0.5 font-label-sm text-label-sm font-semibold text-white">{item.level}</span>}
        </div>
        <h3 className="font-headline-sm text-headline-sm">{item.title}</h3>
        <div className="mt-1 grid grid-cols-3 gap-2">
          {(
            [
              ["Impacto", item.value || "Sin datos", "text-tertiary-fixed-dim"],
              ["Confianza", item.confPct, ""],
              ["Límite", item.deadline, ""],
            ] as const
          ).map(([label, value, tone]) => (
            <div key={label} className="flex flex-col">
              <span className="font-label-sm text-label-sm font-normal text-surface-variant">{label}</span>
              <span className={`text-[12px] font-bold leading-4 ${tone}`}>{value}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-col gap-3 px-4 py-3.5">
        {analysis.status === "loading" && <p className="m-0 text-[13px] leading-[19px] text-on-surface-variant">Cargando análisis…</p>}
        {analysis.status === "soon" && <p className="m-0 text-[13px] leading-[19px] text-on-surface-variant">{SOON_TEXT}</p>}
        {analysis.status === "error" && <p className="m-0 text-[13px] leading-[19px] text-on-surface-variant">No se pudo cargar el análisis: {analysis.message}</p>}
        {sections.map((s) => (
          <div key={s.label} className="flex flex-col gap-1">
            <span className="flex items-center gap-1.5 font-label-md text-label-md uppercase" style={{ color: s.color }}>
              <span aria-hidden="true" className="material-symbols-outlined text-[16px]">{s.icon}</span>
              {s.label}
            </span>
            {s.items.map((t, i) => (
              <p key={i} className="m-0 pl-[22px] text-[13px] leading-[19px] text-on-surface">• {t}</p>
            ))}
          </div>
        ))}
      </div>
      {open && (
        <div className="flex gap-2 px-4 pb-4">
          <button
            type="button"
            disabled={item.readOnly || busy}
            onClick={() => onApprove(item)}
            className="flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-full bg-secondary font-body-md text-body-md font-semibold text-white shadow-[0_4px_6px_-1px_rgba(122,86,73,.2)] disabled:opacity-40"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[18px]">check</span>
            {item.kind === "approval" ? "Aprobar" : "Aceptar"}
          </button>
          <button
            type="button"
            disabled={item.readOnly || busy}
            onClick={() => onReject(item)}
            className="flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-full bg-surface-container-high font-body-md text-body-md font-medium text-primary disabled:opacity-40"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-secondary">close</span>
            Rechazar
          </button>
        </div>
      )}
      {open && item.readOnly && <p className="m-0 px-4 pb-4 font-label-sm text-label-sm text-on-surface-variant">{SOON_TEXT}: esta línea no tiene una propuesta decidible.</p>}
      {!open && (
        <p className="m-0 flex items-center gap-1.5 px-4 pb-4 font-label-md text-label-md normal-case tracking-normal text-secondary">
          <span aria-hidden="true" className="material-symbols-outlined text-[16px]">task_alt</span>
          Decisión registrada
        </p>
      )}
    </article>
  );
}
