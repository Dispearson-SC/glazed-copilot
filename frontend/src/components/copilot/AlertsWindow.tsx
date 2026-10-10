import { filterWarnings, SOON_TEXT, type WarningItem } from "../../data/copilot";
import { FilterChips } from "./MemoriesWindow";

export const ALERT_FILTERS = [
  ["todas", "Todas"],
  ["operacion", "Operación"],
  ["datos", "Datos e integridad"],
  ["auto", "Automáticas"],
] as const;

const TONES = {
  warn: "bg-[rgba(185,133,86,.18)] text-on-tertiary-fixed-variant",
  info: "bg-surface-container-high text-on-surface-variant",
} as const;

/** Advertencias window: what the system detected, with a question shortcut to the chat. */
export default function AlertsWindow({
  warnings,
  filter,
  onFilter,
  onAsk,
}: {
  warnings: WarningItem[];
  filter: string;
  onFilter: (f: string) => void;
  onAsk: (w: WarningItem) => void;
}) {
  const shown = filterWarnings(warnings, filter);
  return (
    <main className="mx-auto flex w-full max-w-[640px] flex-col gap-4 px-4 pb-28 pt-[68px]">
      <header className="flex flex-col gap-1 pt-3">
        <span className="font-label-md text-label-md uppercase tracking-[0.05em] text-on-tertiary-container">Centinela · Auditor · Abastecimiento</span>
        <h1 className="m-0 font-headline-lg text-headline-lg tracking-tight text-primary">Advertencias</h1>
        <p className="m-0 font-body-md text-body-md text-on-surface-variant">Todo lo que el sistema detectó, ordenado por impacto en dinero.</p>
      </header>
      <FilterChips options={ALERT_FILTERS} value={filter} onChange={onFilter} />
      {shown.map((w) => (
        <article key={w.id} className="flex flex-col gap-2 rounded-[18px] border border-partition/60 bg-white p-4 shadow-card">
          <div className="flex items-start gap-3">
            <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full ${TONES[w.tone]}`}>
              <span aria-hidden="true" className="material-symbols-outlined text-[20px]">{w.icon}</span>
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <div className="flex items-center justify-between gap-2">
                <span className={`rounded-full px-2 py-px font-label-sm text-label-sm font-semibold ${TONES[w.tone]}`}>{w.toneLabel}</span>
                <span className="font-label-sm text-label-sm font-normal text-on-surface-variant">{w.time}</span>
              </div>
              <h3 className="m-0 mt-0.5 font-body-lg text-[15px] font-semibold leading-[21px] text-primary">{w.title}</h3>
              <p className="m-0 text-[13px] leading-[19px] text-on-surface-variant">{w.body}</p>
            </div>
          </div>
          <div className="flex items-center justify-between gap-2 pl-12">
            <span className="font-label-sm text-label-sm font-normal text-outline">{w.agent ?? "Agente no informado"}</span>
            <button
              type="button"
              onClick={() => onAsk(w)}
              className="flex min-h-[44px] items-center gap-1 rounded-full bg-surface-container px-3 text-[12px] font-semibold leading-4 text-secondary"
            >
              <span aria-hidden="true" className="material-symbols-outlined text-[16px]">forum</span>
              Preguntar
            </button>
          </div>
        </article>
      ))}
      {shown.length === 0 && (
        <p className="m-0 rounded-[18px] bg-surface-container p-4 text-center text-[13px] leading-[19px] text-on-surface-variant">
          {filter === "auto" ? `Sin acciones automáticas todavía. ${SOON_TEXT}.` : "Sin advertencias por ahora"}
        </p>
      )}
    </main>
  );
}
