import { useState } from "react";
import { dayMonth, money, weekdayShort } from "../format";

export type BarKind = "actual" | "today" | "forecast" | "nodata";

export interface ActivityPoint {
  date: string;
  kind: BarKind;
  value: number | null;
}

const MAX_PX = 112;

const barClass: Record<BarKind, string> = {
  actual: "bg-surface-container group-hover:bg-outline-variant",
  today: "bg-secondary group-hover:bg-primary shadow-sm",
  forecast: "bg-on-tertiary-container group-hover:bg-secondary",
  nodata: "bg-surface-container border-dashed",
};

const labelClass: Record<BarKind, string> = {
  actual: "text-on-surface-variant",
  today: "text-primary font-bold",
  forecast: "text-on-surface font-semibold",
  nodata: "text-on-surface-variant",
};

const styleOf = (p: ActivityPoint): BarKind => (p.value == null && p.kind !== "forecast" ? "nodata" : p.kind);

export default function ActivityChart({ points, model }: { points: ActivityPoint[]; model?: string | null }) {
  const today = points.find((p) => p.kind === "today")?.date ?? points[0]?.date;
  const [hover, setHover] = useState<string | null>(null);
  const active = points.find((p) => p.date === hover) ?? points.find((p) => p.date === today);
  const max = Math.max(1, ...points.map((p) => p.value ?? 0));
  return (
    <section data-testid="activity-chart" className="bg-surface-container-lowest rounded-[18px] p-space-lg shadow-sm shadow-primary/5 flex flex-col gap-space-md">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-headline-sm text-headline-sm text-primary">Ventas por día</h2>
          <p className="font-label-sm text-label-sm text-on-surface-variant">
            Ventas netas de los últimos 7 días y proyección
          </p>
        </div>
        <span className="px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-sm text-label-sm">
          Intervalo 1 día
        </span>
      </div>
      <div className="flex flex-col gap-space-sm pt-2">
        {active && (
          <div className="flex items-center justify-center">
            <div
              data-testid="activity-tooltip"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary text-surface-bright font-label-sm text-label-sm shadow-sm animate-pulse"
            >
              <span aria-hidden="true" className="material-symbols-outlined text-[14px] text-tertiary-fixed-dim">calendar_today</span>
              <span className="font-semibold capitalize">{weekdayShort(active.date)} {dayMonth(active.date)}</span>
              <span>
                • {active.value == null ? "sin datos" : money(active.value)}
                {active.kind === "forecast" ? " (proyección)" : active.value == null ? "" : " (real)"}
              </span>
            </div>
          </div>
        )}
        <div className="w-full h-36 flex items-end justify-between px-1 pt-4 pb-2">
          {points.map((p) => (
            <div
              key={p.date}
              data-testid={`activity-col-${p.date}`}
              onMouseEnter={() => setHover(p.date)}
              onMouseLeave={() => setHover(null)}
              onClick={() => setHover(p.date)}
              className={`flex-1 flex flex-col items-center gap-2 group cursor-pointer ${p.kind === "forecast" ? "opacity-60" : ""} ${p.kind === "today" ? "relative" : ""}`}
            >
              <div
                data-testid={`activity-bar-${p.date}`}
                data-kind={p.kind}
                title={`${p.date}: ${p.value == null ? "sin datos" : money(p.value)}${p.kind === "forecast" ? " (proyección)" : ""}`}
                className={`w-full max-w-[28px] rounded-t-lg transition-all ${barClass[styleOf(p)]}`}
                style={{ height: `${p.value == null ? 24 : Math.max(4, Math.round((p.value / max) * MAX_PX))}px` }}
              ></div>
              <span className={`font-label-sm text-label-sm capitalize ${labelClass[p.kind === "today" ? "today" : styleOf(p)]}`}>
                {p.kind === "today" ? "hoy" : weekdayShort(p.date)}
              </span>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between pt-2 border-t-0 text-on-surface-variant font-label-sm text-label-sm">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-secondary"></span>
            Día mostrado
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-on-tertiary-container"></span>
            Proyección
          </span>
        </div>
        {model && (
          <p data-testid="activity-model" className="font-label-sm text-label-sm text-on-surface-variant">
            Modelo de proyección: {model}
          </p>
        )}
      </div>
    </section>
  );
}
