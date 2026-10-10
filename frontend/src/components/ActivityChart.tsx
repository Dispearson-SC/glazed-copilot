const HOURS = ["07h", "09h", "11h", "13h", "15h", "17h", "19h"];

/** "Actividad de hoy" (Main.dc.html): revenue and traffic by hour. The backend serves no hourly data, so the bars are empty. */
export default function ActivityChart() {
  return (
    <section data-testid="activity-chart" className="bg-surface-container-lowest rounded-[18px] p-space-lg shadow-sm shadow-primary/5 flex flex-col gap-space-md">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-headline-sm text-headline-sm text-primary">Actividad de hoy</h2>
          <p className="font-label-sm text-label-sm text-on-surface-variant">Distribución de ingresos y afluencia por hora</p>
        </div>
        <span className="px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-sm text-label-sm">Intervalo 2h</span>
      </div>
      <div className="flex flex-col gap-space-sm pt-2">
        <div className="flex items-center justify-center">
          <div data-testid="activity-pill" className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary text-surface-bright font-label-sm text-label-sm shadow-sm">
            <span aria-hidden="true" className="material-symbols-outlined text-[14px] text-tertiary-fixed-dim">wb_sunny</span>
            <span className="font-semibold">Sin datos</span>
          </div>
        </div>
        <div className="w-full h-36 flex items-end justify-between px-1 pt-4 pb-2">
          {HOURS.map((h) => (
            <div key={h} className="flex-1 flex flex-col items-center gap-2">
              <div className="w-full max-w-[28px] h-6 rounded-t-lg bg-surface-container"></div>
              <span className="font-label-sm text-label-sm text-on-surface-variant">{h}</span>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between pt-2 text-on-surface-variant font-label-sm text-label-sm">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-secondary"></span>
            Pico registrado (mañana)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-on-tertiary-container"></span>
            Turno actual
          </span>
        </div>
      </div>
    </section>
  );
}
