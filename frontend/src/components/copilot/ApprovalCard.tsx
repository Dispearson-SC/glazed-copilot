import type { DecisionItem } from "../../data/copilot";
import PromoBlock from "./PromoBlock";

/** "Se necesita aprobación / opinión": the only action is to analyze it with the copilot. */
export default function ApprovalCard({ item, onAnalyze }: { item: DecisionItem; onAnalyze: (i: DecisionItem) => void }) {
  return (
    <article className="flex flex-col gap-2.5 rounded-[18px] border border-partition/60 bg-white p-4 shadow-card">
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1 rounded-full bg-[rgba(185,133,86,.15)] px-2.5 py-[3px] font-label-sm text-label-sm font-semibold text-on-tertiary-fixed-variant">
          <span aria-hidden="true" className="material-symbols-outlined text-[14px]">{item.icon}</span>
          {item.level}
        </span>
        <span className="inline-flex items-center gap-1 font-label-sm text-label-sm font-normal text-on-surface-variant">
          <span aria-hidden="true" className="material-symbols-outlined text-[14px]">schedule</span>
          {item.deadline}
        </span>
      </div>
      <h3 className="m-0 font-body-lg text-[16px] font-semibold leading-[22px] text-primary">{item.title}</h3>
      {item.kinds && item.kinds.length > 0 && (
        <ul aria-label="Tipos de decisión" className="m-0 flex list-none flex-wrap gap-1.5 p-0">
          {item.kinds.map((k) => (
            <li key={k} className="rounded-full bg-surface-container px-2.5 py-0.5 font-label-sm text-label-sm font-semibold text-secondary">{k}</li>
          ))}
        </ul>
      )}
      {item.promo && <PromoBlock promo={item.promo} />}
      {item.summary && <p className="m-0 text-[13px] leading-[19px] text-on-surface-variant">{item.summary}</p>}
      <div className="flex items-center gap-3">
        <span className="font-headline-sm text-headline-sm font-bold text-primary">{item.value || "Sin datos"}</span>
        <div className="flex flex-1 flex-col gap-1">
          <div className="flex justify-between font-label-sm text-label-sm font-normal text-on-surface-variant">
            <span>{item.confLabel}</span>
            <span className="font-bold text-primary">{item.confPct}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-container">
            <div className="h-full rounded-full bg-on-tertiary-container" style={{ width: item.confPct.endsWith("%") ? item.confPct : "0%" }} />
          </div>
        </div>
      </div>
      <button
        type="button"
        onClick={() => onAnalyze(item)}
        className="flex min-h-[48px] w-full items-center justify-center gap-2 rounded-full bg-primary-container font-body-md text-body-md font-semibold text-surface shadow-hero"
      >
        <span aria-hidden="true" className="material-symbols-outlined text-[20px] text-tertiary-fixed-dim">query_stats</span>
        Analizar con el copiloto
      </button>
    </article>
  );
}
