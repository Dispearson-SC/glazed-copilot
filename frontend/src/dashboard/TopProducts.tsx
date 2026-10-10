import type { DaySummary } from "../types";
import { money } from "./format";

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
        <span className="px-2.5 py-0.5 rounded-full bg-surface-container text-secondary font-label-md text-label-md">Top 3</span>
      </div>
      {skus.length === 0 && <p className="text-on-surface-variant text-body-md px-1">Sin datos</p>}
      <div className="flex flex-col gap-space-xs mt-1">
        {skus.map((p, i) => (
          <article
            key={p.sku}
            data-testid={`top-product-${i + 1}`}
            className="bg-surface-container-lowest rounded-[18px] p-space-sm flex items-center gap-space-sm shadow-sm shadow-primary/5"
          >
            <span
              aria-hidden="true"
              className="w-12 h-12 rounded-[14px] flex-shrink-0 bg-surface-container text-secondary flex items-center justify-center font-headline-sm text-headline-sm"
            >
              {i + 1}
            </span>
            <div className="flex-1 min-w-0 flex flex-col gap-1.5">
              <div className="flex items-start justify-between gap-1">
                <h3 className="font-body-lg text-body-lg text-primary font-semibold truncate leading-snug">{p.product_name}</h3>
                <span className="font-headline-sm text-headline-sm text-primary font-bold flex-shrink-0">{money(p.net_sales)}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 rounded-full bg-surface-container overflow-hidden">
                  <div
                    className="h-full rounded-full bg-secondary"
                    style={{ width: `${best > 0 ? Math.round((p.net_sales / best) * 100) : 0}%` }}
                  ></div>
                </div>
                <span className="font-label-sm text-label-sm text-on-surface font-medium whitespace-nowrap">{p.units} uds</span>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
