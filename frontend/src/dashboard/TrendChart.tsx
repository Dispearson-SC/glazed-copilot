import { ErrorBox } from "../components";
import type { DaySummary } from "../types";
import { money, weekdayShort } from "./format";

const MAX_PX = 112;

export default function TrendChart({ days, selected, error }: { days: DaySummary[] | null; selected: string; error: Error | null }) {
  const max = Math.max(0, ...(days ?? []).map((d) => d.totals?.net_sales ?? 0));
  return (
    <section className="bg-surface-container-lowest rounded-[18px] p-space-lg shadow-sm shadow-primary/5 flex flex-col gap-space-md">
      <div>
        <h2 className="font-headline-sm text-headline-sm text-primary">Últimos 7 días</h2>
        <p className="font-label-sm text-label-sm text-on-surface-variant">Ventas netas por día</p>
      </div>
      <ErrorBox error={error} />
      {days && (
        <div className="w-full h-36 flex items-end justify-between px-1 pt-4 pb-2 gap-1">
          {days.map((d) => {
            const sales = d.totals?.net_sales;
            const dim = d.date === selected ? "" : "opacity-50";
            return (
              <div key={d.date} className={`flex-1 flex flex-col items-center gap-2 ${dim}`}>
                {sales == null ? (
                  <div
                    data-testid={`trend-nodata-${d.date}`}
                    className="w-full max-w-[28px] h-6 rounded-t-lg border border-dashed border-outline-variant text-[9px] leading-none text-on-surface-variant flex items-center justify-center text-center"
                  >
                    sin datos
                  </div>
                ) : (
                  <div
                    data-testid={`trend-bar-${d.date}`}
                    title={`${d.date}: ${money(sales)}`}
                    className={`w-full max-w-[28px] rounded-t-lg ${d.date === selected ? "bg-on-tertiary-container" : "bg-secondary"}`}
                    style={{ height: `${max > 0 ? Math.max(4, Math.round((sales / max) * MAX_PX)) : 4}px` }}
                  ></div>
                )}
                <span className="font-label-sm text-label-sm text-on-surface-variant capitalize">{weekdayShort(d.date)}</span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
