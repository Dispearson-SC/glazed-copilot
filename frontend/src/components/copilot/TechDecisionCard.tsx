import { SOON_TEXT, type DecisionItem } from "../../data/copilot";

/** "Decisiones técnicas": quantities and dates calculated by the backend, ready to accept. */
export default function TechDecisionCard({
  item,
  menuOpen,
  busy,
  onAccept,
  onReject,
  onToggleMenu,
  onDialog,
}: {
  item: DecisionItem;
  menuOpen: boolean;
  busy: boolean;
  onAccept: (i: DecisionItem) => void;
  onReject: (i: DecisionItem) => void;
  onToggleMenu: (i: DecisionItem) => void;
  onDialog: (i: DecisionItem) => void;
}) {
  const subtitle = [item.supplier, item.arrive, item.cost].filter(Boolean).join(" · ");
  return (
    <article className="relative flex flex-col gap-2.5 rounded-[18px] border border-partition/60 bg-white p-4 shadow-card">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-surface-container text-secondary">
          <span aria-hidden="true" className="material-symbols-outlined text-[22px]">{item.icon}</span>
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="m-0 font-body-lg text-[16px] font-semibold leading-[22px] text-primary">{item.title}</h3>
          {subtitle && <p className="m-0 font-label-sm text-label-sm font-normal text-on-surface-variant">{subtitle}</p>}
        </div>
      </div>
      {item.why && <p className="m-0 text-[13px] leading-[19px] text-on-surface">{item.why}</p>}
      <div className="flex flex-wrap gap-1.5">
        {item.chips.map((c) => (
          <span key={c} className="inline-flex items-center gap-1 rounded-full bg-[rgba(185,133,86,.15)] px-2.5 py-[3px] font-label-sm text-label-sm font-semibold text-on-tertiary-fixed-variant">
            <span aria-hidden="true" className="material-symbols-outlined text-[14px]">trending_down</span>
            {c}
          </span>
        ))}
        <span className="inline-flex items-center gap-1 rounded-full bg-surface-container-high px-2.5 py-[3px] font-label-sm text-label-sm font-semibold text-primary">
          <span aria-hidden="true" className="material-symbols-outlined text-[14px]">schedule</span>
          {item.deadline}
        </span>
        <span className="inline-flex items-center rounded-full bg-surface-container px-2.5 py-[3px] font-label-sm text-label-sm text-on-surface-variant">Confianza {item.confPct}</span>
      </div>
      {item.warn && (
        <p className="m-0 flex gap-1.5 rounded-xl bg-surface-container px-3 py-2 text-[12px] leading-4 text-on-surface-variant">
          <span aria-hidden="true" className="material-symbols-outlined text-[16px] text-on-tertiary-container">info</span>
          {item.warn}
        </p>
      )}
      {item.readOnly && <p className="m-0 font-label-sm text-label-sm text-on-surface-variant">{SOON_TEXT}: esta línea del plan aún no se puede decidir.</p>}
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={item.readOnly || busy}
          onClick={() => onAccept(item)}
          className="flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-full bg-secondary font-body-md text-body-md font-semibold text-white shadow-[0_4px_6px_-1px_rgba(122,86,73,.2),0_2px_4px_-2px_rgba(122,86,73,.2)] disabled:opacity-40"
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[18px]">check</span>
          Aceptar
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
        <button
          type="button"
          onClick={() => onToggleMenu(item)}
          aria-label="Más opciones"
          aria-expanded={menuOpen}
          className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full border border-surface-container-high bg-white p-0 text-on-surface-variant"
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[20px]">more_vert</span>
        </button>
      </div>
      {menuOpen && (
        <div role="menu" className="absolute bottom-16 right-4 z-[5] min-w-[248px] rounded-2xl border border-surface-container-high bg-white p-1.5 shadow-sheet">
          <button
            type="button"
            role="menuitem"
            onClick={() => onDialog(item)}
            disabled={item.readOnly}
            className="flex min-h-[44px] w-full items-center gap-2.5 rounded-xl bg-surface px-3 text-left font-body-md text-body-md font-medium text-primary disabled:opacity-40"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[20px] text-secondary">forum</span>
            Dialogar acerca de esta decisión
          </button>
        </div>
      )}
    </article>
  );
}
