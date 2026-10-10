import type { DaySummary } from "../types";
import { NO_DATA, money, signedPct } from "../format";

export default function HeroCard({ summary }: { summary: DaySummary }) {
  const sales = summary.totals?.net_sales;
  const vs = summary.vs_same_weekday_avg;
  const hasData = sales != null;
  const progress = hasData && vs && vs.baseline_net_sales > 0 ? Math.round((sales / vs.baseline_net_sales) * 100) : null;
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
            Ventas de hoy
          </span>
          <div className="w-9 h-9 rounded-full bg-surface-container-lowest/10 flex items-center justify-center text-tertiary-fixed-dim">
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">coffee_maker</span>
          </div>
        </div>
        <div className="flex flex-col gap-space-xs">
          <div className="flex items-baseline justify-between flex-wrap gap-2">
            <span className="font-display-hero-mobile text-display-hero-mobile text-surface-bright tracking-tight font-bold">
              {hasData ? money(sales) : NO_DATA}
            </span>
            {hasData && vs && (
              <div
                data-testid="hero-delta"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-on-tertiary-container text-surface-container-lowest font-label-md text-label-md shadow-sm"
              >
                <span aria-hidden="true" className="material-symbols-outlined text-[15px] font-bold">
                  {vs.delta_pct >= 0 ? "north_east" : "south_east"}
                </span>
                <span>{signedPct(vs.delta_pct)} vs promedio</span>
              </div>
            )}
          </div>
          <p className="font-label-sm text-label-sm text-surface-variant font-normal">Ventas netas del día en la sucursal</p>
        </div>
        {hasData && vs && progress !== null && (
          <div className="pt-space-xs mt-space-xs flex flex-col gap-1.5">
            <div className="flex justify-between items-center font-label-sm text-label-sm">
              <span className="text-surface-container-high">
                Promedio mismo día ({vs.weeks_used} sem): {money(vs.baseline_net_sales)}
              </span>
              <span data-testid="hero-progress" className="text-tertiary-fixed-dim font-bold">{progress}% del promedio</span>
            </div>
            <div className="w-full h-2 rounded-full bg-surface-container-lowest/15 overflow-hidden">
              <div
                data-testid="hero-bar"
                className="h-full rounded-full bg-tertiary-fixed-dim transition-all duration-1000 ease-out"
                style={{ width: `${Math.min(100, progress)}%` }}
              ></div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
