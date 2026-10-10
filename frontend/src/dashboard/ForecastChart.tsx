import type { ForecastResponse } from "../types";
import { money, weekdayShort } from "./format";

const MAX_PX = 112;
const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

export default function ForecastChart({ forecast }: { forecast: ForecastResponse }) {
  const { points, as_of: today, metrics_to_date: m } = forecast;
  // Look-ahead guard: an actual dated after as_of is never drawn, whatever the payload says.
  const actualOf = (p: (typeof points)[number]) => (p.date <= today ? p.actual : null);
  const max = Math.max(1, ...points.flatMap((p) => [p.p90, p.forecast, actualOf(p) ?? 0]));
  const px = (v: number) => Math.round((v / max) * MAX_PX);
  return (
    <section data-testid="forecast-chart" className="bg-surface-container-lowest rounded-[18px] p-space-lg shadow-sm shadow-primary/5 flex flex-col gap-space-md">
      <div>
        <h2 className="font-headline-sm text-headline-sm text-primary">Ventas: real y proyección</h2>
        <p className="font-label-sm text-label-sm text-on-surface-variant">
          Proyección ({forecast.unit}) con rango p10–p90 · <span data-testid="forecast-model">{forecast.model}</span>
        </p>
      </div>
      <div className="w-full flex items-end justify-between px-1 pt-4 gap-1">
        {points.map((p) => {
          const actual = actualOf(p);
          const isToday = p.date === today;
          const future = p.date > today;
          return (
            <div key={p.date} data-testid={`fc-col-${p.date}`} className={`flex-1 flex flex-col items-center gap-1 ${future ? "opacity-90" : ""}`}>
              <span className="text-[9px] leading-none text-secondary font-bold h-3">{isToday ? "hoy" : ""}</span>
              <div className="relative w-full max-w-[28px]" style={{ height: `${MAX_PX}px` }}>
                <div
                  data-testid={`fc-band-${p.date}`}
                  title={`p10–p90: ${money(p.p10)} – ${money(p.p90)}`}
                  className="absolute left-0 right-0 bg-secondary/20 rounded"
                  style={{ bottom: `${px(p.p10)}px`, height: `${Math.max(2, px(p.p90) - px(p.p10))}px` }}
                />
                {actual !== null && (
                  <div
                    data-testid={`fc-actual-${p.date}`}
                    title={`${p.date} real: ${money(actual)}`}
                    className="absolute bottom-0 left-1 right-1 bg-on-tertiary-container rounded-t"
                    style={{ height: `${Math.max(2, px(actual))}px` }}
                  />
                )}
                <div
                  data-testid={`fc-forecast-${p.date}`}
                  title={`${p.date} proyección: ${money(p.forecast)}`}
                  className="absolute left-0 right-0 h-0.5 bg-secondary"
                  style={{ bottom: `${px(p.forecast)}px` }}
                />
              </div>
              <span className="font-label-sm text-label-sm text-on-surface-variant capitalize">{weekdayShort(p.date)}</span>
              {p.censored && (
                <span
                  data-testid={`fc-censored-${p.date}`}
                  title={`Quiebre${p.stockout_hours !== undefined ? ` (${p.stockout_hours} h sin producto)` : ""}: la venta real subestima la demanda`}
                  className="text-[9px] leading-none text-error"
                >
                  quiebre
                </span>
              )}
            </div>
          );
        })}
      </div>
      <p className="font-label-sm text-label-sm text-on-surface-variant flex gap-3">
        <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-on-tertiary-container" />Real</span>
        <span className="inline-flex items-center gap-1"><span className="w-3 h-0.5 bg-secondary" />Proyección</span>
        <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-secondary/20" />p10–p90</span>
      </p>
      <p data-testid="forecast-metrics" className="text-body-md text-on-surface">
        Error (WAPE) {pct(m.wape)} vs línea base {pct(m.wape_baseline)} · sesgo {pct(m.bias)} · el rango cubre {Math.round(m.coverage_p10_p90 * 100)}% de los días · {m.n_days} días evaluados
      </p>
    </section>
  );
}
