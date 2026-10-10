import { ErrorBox } from "../components";
import { asRange, rangeOrValue, usd } from "../issues";
import type { BriefOrderLine, Briefing, OrderLine, OrderPlan, Range3 } from "../types";

const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
const cardCls = "bg-surface-container-lowest rounded-[18px] p-space-lg shadow-sm shadow-primary/5 flex flex-col gap-space-md";
const quiet = "text-body-md text-on-surface-variant";

function sumRanges(values: (number | Range3 | undefined)[]): Range3 | null {
  const rs = values.filter((v): v is number | Range3 => v !== undefined).map(asRange);
  if (rs.length === 0) return null;
  return rs.reduce((a, r) => ({ low: a.low + r.low, mid: a.mid + r.mid, high: a.high + r.high }), { low: 0, mid: 0, high: 0 });
}

function OrderRow({ group, line }: { group: string; line: BriefOrderLine }) {
  return (
    <li data-testid={`upcoming-${group}-${line.sku}`} className="flex flex-col text-body-md">
      <span className="font-bold">{line.name ?? line.sku}</span>
      <span className="text-on-surface-variant text-label-md">
        {line.supplier_name ?? line.supplier_id ?? ""}
        {line.qty !== undefined && ` · ${line.qty} pzas`}
        {line.cases !== undefined && ` (${line.cases} ${line.cases === 1 ? "caja" : "cajas"})`}
        {line.est_cost_usd !== undefined && ` · ${usd(line.est_cost_usd)}`}
      </span>
      <span className="text-on-surface-variant text-label-md">
        Pedir antes de: {line.order_deadline ?? "—"} · hora no disponible
      </span>
    </li>
  );
}

function OrderGroup({ group, title, empty, lines }: { group: string; title: string; empty: string; lines: BriefOrderLine[] }) {
  return (
    <div data-testid={`upcoming-${group}`} className="flex flex-col gap-space-xs">
      <h3 className="font-label-md text-label-md text-secondary">{title}</h3>
      {lines.length === 0 ? (
        <p className={quiet}>{empty}</p>
      ) : (
        <ul className="flex flex-col gap-space-sm list-none p-0 m-0">
          {lines.map((l) => <OrderRow key={l.sku} group={group} line={l} />)}
        </ul>
      )}
    </div>
  );
}

function Stockouts({ lines }: { lines: OrderLine[] }) {
  const next = lines
    .filter((l) => l.projected_stockout_date)
    .sort((a, b) => a.projected_stockout_date!.localeCompare(b.projected_stockout_date!))
    .slice(0, 5);
  return (
    <div className="flex flex-col gap-space-xs">
      <h3 className="font-label-md text-label-md text-secondary">Próximos quiebres (proyección)</h3>
      {next.length === 0 ? (
        <p className={quiet}>Sin quiebres proyectados</p>
      ) : (
        <ul data-testid="upcoming-stockouts" className="flex flex-col gap-space-sm list-none p-0 m-0">
          {next.map((l) => (
            <li key={l.sku} className="text-body-md">
              <span className="font-bold">{l.name ?? l.sku}</span> · se agota {l.projected_stockout_date}
              <div className="text-on-surface-variant text-label-md">
                Riesgo sin pedir {pct(l.stockout_risk_without_order)}
                {l.stockout_risk_with_order !== undefined && ` · con pedido ${pct(l.stockout_risk_with_order)}`}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function UpcomingCard({ briefing, plan, error }: { briefing: Briefing | null; plan: OrderPlan | null; error: Error | null }) {
  const op = briefing?.snapshot?.order_plan;
  const worst = briefing?.headline?.find((h) => h.key === "worst_supplier");
  const lines = plan?.lines ?? [];
  const waste = sumRanges(lines.map((l) => l.expected_waste_usd));
  const belowMin = (plan?.suppliers ?? []).filter((s) => s.order_value_usd < s.min_order_value);
  return (
    <section data-testid="upcoming" className={cardCls}>
      <div>
        <h2 className="font-headline-sm text-headline-sm text-primary">Lo que viene</h2>
        <p className="font-label-sm text-label-sm text-on-surface-variant">Proyecciones del plan de pedidos; no son ventas reales</p>
      </div>
      <ErrorBox error={error} />
      <OrderGroup group="today" title="Pedidos de hoy" empty="Sin pedidos para hoy" lines={op?.due_today ?? []} />
      <OrderGroup group="tomorrow" title="Pedidos de mañana" empty="Sin pedidos para mañana" lines={op?.due_tomorrow ?? []} />
      <Stockouts lines={lines} />
      {waste && (
        <p data-testid="upcoming-waste" className="text-body-md">
          Merma esperada: <strong>{rangeOrValue(waste)}</strong> (medio {usd(waste.mid)}, suma de las líneas)
        </p>
      )}
      {worst && <p data-testid="upcoming-worst-supplier" className="text-body-md">{worst.text}</p>}
      {belowMin.length > 0 && (
        <ul data-testid="upcoming-min-order" className="flex flex-col gap-1 list-none p-0 m-0 text-body-md">
          {belowMin.map((s) => (
            <li key={s.supplier_id}>
              {s.supplier_name}: pedido {usd(s.order_value_usd)} bajo el mínimo de {usd(s.min_order_value)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
