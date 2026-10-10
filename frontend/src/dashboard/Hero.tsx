import type { DaySummary } from "../types";
import { NO_DATA, longDate, money, signedPct } from "./format";

export default function Hero({ summary }: { summary: DaySummary }) {
  const sales = summary.totals?.net_sales;
  const vs = summary.vs_same_weekday_avg;
  return (
    <section
      data-testid="hero"
      className="relative overflow-hidden rounded-[20px] bg-primary-container text-surface-container-lowest p-space-lg shadow-xl shadow-primary-container/20"
    >
      <div className="absolute -right-12 -top-12 w-48 h-48 rounded-full bg-secondary-container/10 blur-2xl pointer-events-none"></div>
      <div className="absolute -left-12 -bottom-12 w-40 h-40 rounded-full bg-on-tertiary-container/10 blur-2xl pointer-events-none"></div>
      <div className="relative z-10 flex flex-col gap-space-md">
        <div className="flex items-center justify-between">
          <span className="font-label-md text-label-md text-surface-container tracking-wider uppercase">
            Ventas netas del día
          </span>
          <div className="w-9 h-9 rounded-full bg-surface-container-lowest/10 flex items-center justify-center text-tertiary-fixed-dim">
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">payments</span>
          </div>
        </div>
        <div className="flex flex-col gap-space-xs">
          <div className="flex items-baseline justify-between flex-wrap gap-2">
            <span className="font-display-hero-mobile text-display-hero-mobile text-surface-bright tracking-tight font-bold">
              {sales == null ? NO_DATA : money(sales)}
            </span>
            {sales != null && vs && (
              <div
                data-testid="hero-delta"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-on-tertiary-container text-surface-container-lowest font-label-md text-label-md shadow-sm"
              >
                <span aria-hidden="true" className="material-symbols-outlined text-[15px] font-bold">
                  {vs.delta_pct >= 0 ? "trending_up" : "trending_down"}
                </span>
                <span>{signedPct(vs.delta_pct)}</span>
              </div>
            )}
          </div>
          <p className="font-label-sm text-label-sm text-surface-variant font-normal">
            {longDate(summary.date)} ({summary.date})
          </p>
        </div>
        {sales != null && vs && (
          <p className="font-label-sm text-label-sm text-surface-container-high">
            Frente al promedio de {vs.weeks_used} semanas del mismo día ({money(vs.baseline_net_sales)})
          </p>
        )}
      </div>
    </section>
  );
}
