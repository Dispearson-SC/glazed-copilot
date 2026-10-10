import type { DaySummary } from "../types";

const chip = "inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm";

export default function ContextChips({ context }: { context: DaySummary["context"] }) {
  if (!context) return null;
  const w = context.weather;
  return (
    <div className="flex flex-wrap gap-space-xs">
      {context.is_holiday && <span className={chip}>{context.holiday_name || "Feriado"}</span>}
      {context.is_weekend && <span className={chip}>Fin de semana</span>}
      {context.is_school_break && <span className={chip}>Vacaciones escolares</span>}
      {w && (w.temp_max_c != null || w.temp_min_c != null) && (
        <span data-testid="weather" className={chip}>
          <span aria-hidden="true" className="material-symbols-outlined text-[14px]">partly_cloudy_day</span>
          Clima observado: {w.temp_max_c ?? "—"}° / {w.temp_min_c ?? "—"}°
          {w.precip_mm ? ` · ${w.precip_mm} mm` : ""}
        </span>
      )}
    </div>
  );
}
