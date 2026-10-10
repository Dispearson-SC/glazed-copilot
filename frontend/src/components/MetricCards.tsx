import type { DaySummary } from "../types";
import { NO_DATA, avgTicket } from "../format";

export default function MetricCards({ summary }: { summary: DaySummary }) {
  const t = summary.totals;
  const metrics = [
    { id: "transactions", icon: "receipt_long", label: "Pedidos realizados", value: t?.transactions == null ? NO_DATA : String(t.transactions) },
    { id: "avg-ticket", icon: "payments", label: "Ticket promedio", value: t ? avgTicket(t.net_sales, t.transactions) : NO_DATA },
    { id: "units", icon: "local_cafe", label: "Items vendidos", value: t?.units_sold == null ? NO_DATA : String(t.units_sold) },
  ];
  return (
    <section className="grid grid-cols-3 gap-space-sm">
      {metrics.map((m) => (
        <div
          key={m.id}
          data-testid={`metric-${m.id}`}
          className="bg-surface-container-lowest rounded-[16px] p-space-md flex flex-col justify-between shadow-sm shadow-primary/5 hover:shadow-md transition-shadow"
        >
          <div className="w-8 h-8 rounded-full bg-surface-container flex items-center justify-center text-secondary mb-2">
            <span aria-hidden="true" className="material-symbols-outlined text-[18px]">{m.icon}</span>
          </div>
          <div>
            <span className="font-metric-value-sm text-metric-value-sm text-primary block">{m.value}</span>
            <span className="font-label-sm text-label-sm text-on-surface-variant leading-tight block mt-0.5">{m.label}</span>
          </div>
        </div>
      ))}
    </section>
  );
}
