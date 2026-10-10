import type { DaySummary } from "../types";
import { initials, money } from "../format";

const BAR = ["bg-on-tertiary-container", "bg-secondary", "bg-outline"];
const RANK = ["bg-primary text-surface-bright shadow-xs", "bg-surface-container-highest text-primary", "bg-surface-container-highest text-primary"];

export default function TopProducts({ summary }: { summary: DaySummary }) {
  const skus = (summary.top_skus ?? []).slice(0, 3);
  const best = Math.max(0, ...skus.map((s) => s.net_sales));
  return (
    <section className="flex flex-col gap-space-sm">
      <div className="flex items-center justify-between px-1">
        <div>
          <h2 className="font-headline-sm text-headline-sm text-primary">Favoritos del día</h2>
          <p className="font-label-sm text-label-sm text-on-surface-variant">Productos con más ventas</p>
        </div>
        <span className="px-2.5 py-0.5 rounded-full bg-surface-container text-secondary font-label-md text-label-md">
          Top 3
        </span>
      </div>
      {skus.length === 0 && <p className="font-body-md text-body-md text-on-surface-variant px-1">Sin datos</p>}
      <div className="flex flex-col gap-space-xs mt-1">
        {skus.map((p, i) => (
          <article
            key={p.sku}
            data-testid={`top-product-${i + 1}`}
            className="bg-surface-container-lowest rounded-[18px] p-space-sm flex items-center gap-space-sm shadow-sm shadow-primary/5 hover:bg-surface-bright transition-colors"
          >
            <div className="relative w-16 h-16 rounded-[14px] overflow-hidden flex-shrink-0 bg-surface-container flex items-center justify-center">
              <span data-testid="initials" aria-hidden="true" className="font-headline-sm text-headline-sm text-secondary">
                {initials(p.product_name)}
              </span>
              <span
                data-testid="rank"
                className={`absolute top-1 left-1 w-5 h-5 rounded-full flex items-center justify-center font-label-sm text-label-sm font-bold ${RANK[i]}`}
              >
                {i + 1}
              </span>
            </div>
            <div className="flex-1 min-w-0 flex flex-col justify-between py-0.5">
              <div className="flex items-start justify-between gap-1">
                <div className="min-w-0">
                  <h3 className="font-body-lg text-body-lg text-primary font-semibold truncate leading-snug">
                    {p.product_name}
                  </h3>
                  <p className="font-label-sm text-label-sm text-on-surface-variant truncate">
                    {p.units > 0 ? `${money(p.net_sales / p.units)} por unidad` : "Sin unidades"}
                  </p>
                </div>
                <span className="font-headline-sm text-headline-sm text-primary font-bold flex-shrink-0">
                  {money(p.net_sales)}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <div className="flex-1 h-1.5 rounded-full bg-surface-container overflow-hidden">
                  <div
                    className={`h-full rounded-full ${BAR[i]}`}
                    style={{ width: `${best > 0 ? Math.round((p.net_sales / best) * 100) : 0}%` }}
                  ></div>
                </div>
                <span className="font-label-sm text-label-sm text-on-surface font-medium whitespace-nowrap">
                  {p.units} uds.
                </span>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
