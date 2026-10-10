import { useState } from "react";
import { isPlaceholder, type DayKey, type DayView, type InventoryRow, type ScheduledRow } from "../../data/copilot";

/** Rows shown before "Ver todo"; the backend already sorts critical first. */
const INVENTORY_TOP = 10;

const EMPTY = "text-[13px] font-medium leading-[18px] text-on-surface-variant";

const DAYS: { key: DayKey; label: string }[] = [
  { key: "ayer", label: "Ayer" },
  { key: "hoy", label: "Hoy" },
  { key: "manana", label: "Mañana" },
];

const card = "rounded-2xl bg-white p-4 flex flex-col gap-1.5 shadow-card";
const tile = "rounded-2xl bg-white p-3 shadow-[0_1px_2px_rgba(51,27,17,.05)]";

function Tile({ value, label }: { value: string; label: string }) {
  return (
    <div className={tile}>
      <span className={isPlaceholder(value) ? `block ${EMPTY}` : "block text-[18px] font-bold leading-6 text-primary"}>{value}</span>
      <span className="font-label-sm text-label-sm font-normal text-on-surface-variant">{label}</span>
    </div>
  );
}

/** Sucursal window: Ayer / Hoy / Mañana, sales, weather, KPIs, inventory and scheduled purchases. */
export default function BranchWindow({
  storeCode,
  day,
  onDay,
  view,
  inventory,
  inventoryFailed,
  scheduled,
  pendingBuy,
  onGoDecisiones,
}: {
  storeCode: string;
  day: DayKey;
  onDay: (d: DayKey) => void;
  view: DayView | null;
  inventory: InventoryRow[];
  inventoryFailed: boolean;
  scheduled: ScheduledRow[];
  pendingBuy: number;
  onGoDecisiones: () => void;
}) {
  const [showAll, setShowAll] = useState(false);
  if (!view) {
    return (
      <main className="mx-auto w-full max-w-[640px] px-4 pb-28 pt-[112px]">
        <p className="m-0 font-body-md text-body-md text-on-surface-variant">Cargando sucursal…</p>
      </main>
    );
  }
  return (
    <main className="mx-auto flex w-full max-w-[640px] flex-col gap-5 px-4 pb-28 pt-[104px]">
      <header className="flex flex-col gap-3 pt-3">
        <div>
          <span className="font-label-md text-label-md uppercase tracking-[0.05em] text-on-tertiary-container">Sucursal {storeCode}</span>
          <h1 className="m-0 font-headline-lg text-headline-lg tracking-tight text-primary">{view.title}</h1>
          <p className="m-0 font-body-md text-body-md text-on-surface-variant">{view.date}</p>
        </div>
        <div role="tablist" aria-label="Día" className="flex gap-2">
          {DAYS.map((d) => (
            <button
              key={d.key}
              type="button"
              role="tab"
              aria-selected={day === d.key}
              onClick={() => onDay(d.key)}
              className={`min-h-[44px] flex-1 rounded-full text-[13px] font-semibold leading-[18px] ${day === d.key ? "bg-primary-container text-surface" : "bg-partition text-primary"}`}
            >
              {d.label}
            </button>
          ))}
        </div>
      </header>

      <section className="relative overflow-hidden rounded-[20px] bg-primary-container p-6 text-white shadow-hero">
        <div aria-hidden="true" className="absolute -right-12 -top-12 h-48 w-48 rounded-full bg-secondary-container/10 blur-[40px]" />
        <div className="relative flex flex-col gap-3.5">
          <div className="flex items-center justify-between">
            <span className="font-label-md text-label-md uppercase tracking-[0.05em] text-surface-container">Ventas esperadas</span>
            <span className="rounded-full bg-white/10 px-2 py-0.5 font-label-sm text-label-sm font-semibold text-tertiary-fixed-dim">{view.conf}</span>
          </div>
          <div>
            <span className={isPlaceholder(view.expected) ? "block text-[16px] font-medium leading-9 text-surface-variant" : "block font-headline-lg text-[30px] font-bold leading-9 tracking-tight text-surface"}>{view.expected}</span>
            <span className="font-label-sm text-label-sm font-normal text-surface-variant">Rango probable {view.range ?? "Sin datos"}</span>
          </div>
          <div className="h-px bg-white/[.12]" />
          <div className="flex items-center justify-between gap-2">
            <div className="flex flex-col">
              <span className="font-label-sm text-label-sm font-normal text-surface-variant">Ventas reales</span>
              <span className={isPlaceholder(view.real) ? "text-[14px] font-medium leading-6 text-surface-variant" : "text-[18px] font-bold leading-6 text-surface"}>{view.real}</span>
            </div>
            <span className={`rounded-full px-2.5 py-1 font-label-md text-label-md normal-case tracking-normal text-white ${view.realKnown ? "bg-on-tertiary-container" : "bg-white/[.14]"}`}>{view.realNote}</span>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-2">
        <div className={card}>
          <div className="flex items-center gap-2">
            <span aria-hidden="true" className="material-symbols-outlined text-[22px] text-on-tertiary-container">{view.weather.icon}</span>
            <span className="font-label-sm text-label-sm font-semibold text-on-surface-variant">Clima · {view.weather.tag}</span>
          </div>
          <span className={isPlaceholder(view.weather.temp) ? EMPTY : "text-[22px] font-bold leading-7 text-primary"}>{view.weather.temp}</span>
          <span className="text-[12px] leading-4 text-on-surface-variant">{view.weather.text}</span>
          <span className="self-start rounded-full bg-[rgba(185,133,86,.15)] px-2 py-0.5 font-label-sm text-label-sm font-semibold text-on-tertiary-fixed-variant">{view.weather.effect}</span>
        </div>
        <div className={card}>
          <div className="flex items-center gap-2">
            <span aria-hidden="true" className="material-symbols-outlined text-[22px] text-on-tertiary-container">calendar_month</span>
            <span className="font-label-sm text-label-sm font-semibold text-on-surface-variant">Contexto del día</span>
          </div>
          <span className={isPlaceholder(view.traffic.value) ? EMPTY : "text-[22px] font-bold leading-7 text-primary"}>{view.traffic.value}</span>
          <span className="text-[12px] leading-4 text-on-surface-variant">{view.traffic.caption}</span>
          <span className="text-[12px] leading-4 text-on-surface-variant">{view.context}</span>
        </div>
      </section>

      <section className="grid grid-cols-3 gap-2">
        <Tile value={view.orders.value} label={view.orders.label} />
        <Tile value={view.ticket.value} label="Ticket promedio" />
        <Tile value={view.conversion.value} label="Conversión" />
      </section>

      <section className="grid grid-cols-2 gap-2">
        {[view.waste, view.lost].map((s) => (
          <div key={s.label} className="rounded-2xl bg-surface-container-high p-3.5">
            <span className="font-label-sm text-label-sm font-semibold text-on-surface-variant">{s.label}</span>
            <span className={isPlaceholder(s.value) ? `block ${EMPTY}` : "block text-[18px] font-bold leading-6 text-primary"}>{s.value}</span>
            <span className="font-label-sm text-label-sm font-normal text-on-surface-variant">{s.sub}</span>
          </div>
        ))}
      </section>

      <section className="flex flex-col gap-3.5 rounded-[18px] bg-white px-4 py-5 shadow-card">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="m-0 font-headline-sm text-headline-sm text-primary">Inventario y salida</h2>
            <p className="m-0 font-label-sm text-label-sm font-normal text-on-surface-variant">Actual · salida pronosticada hoy · programado</p>
          </div>
          <span className="flex-shrink-0 rounded-full bg-surface-container px-2.5 py-0.5 font-label-sm text-label-sm font-semibold text-secondary">Proyección desde hoy</span>
        </div>
        {inventoryFailed && <p className="m-0 text-[13px] text-on-surface-variant">Sin datos de inventario</p>}
        {(showAll ? inventory : inventory.slice(0, INVENTORY_TOP)).map((r) => (
          <div key={r.sku} data-row className="flex flex-col gap-1.5 border-b border-partition/70 pb-3">
            <div className="flex items-center justify-between gap-2">
              <span className="font-body-md text-body-md font-semibold text-primary">{r.name}</span>
              <span title={r.reason || undefined} className={`flex-shrink-0 rounded-full px-2 py-0.5 font-label-sm text-label-sm font-semibold ${r.status === "critical" ? "bg-error-container text-on-error-container" : r.status === "watch" ? "bg-[rgba(185,133,86,.18)] text-on-tertiary-fixed-variant" : "bg-surface-container-high text-on-surface-variant"}`}>{r.statusLabel || r.cover}</span>
            </div>
            {r.display && <p className="m-0 font-label-sm text-label-sm font-normal text-on-surface-variant">{r.display}</p>}
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-container">
              <div className="h-full rounded-full bg-on-tertiary-container" style={{ width: `${r.fill}%` }} />
            </div>
            <div className="grid grid-cols-3 gap-2 font-label-sm text-label-sm font-normal text-on-surface-variant">
              <span>Actual <b className="text-on-surface">{r.now}</b></span>
              <span>Salida <b className="text-on-surface">{r.out}</b></span>
              <span>Compra <b className="text-on-surface">{r.buy}</b></span>
            </div>
          </div>
        ))}
        {inventory.length > INVENTORY_TOP && (
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            className="min-h-[44px] self-center rounded-full border border-partition/60 bg-elevation px-4 font-label-md text-label-md font-semibold text-secondary"
          >
            {showAll ? "Ver menos" : `Ver todo (${inventory.length})`}
          </button>
        )}
        {!inventoryFailed && inventory.length === 0 && <p className="m-0 text-[13px] text-on-surface-variant">Sin datos</p>}
      </section>

      <section className="flex flex-col gap-2">
        <div className="px-1">
          <h2 className="m-0 font-headline-sm text-headline-sm text-primary">Programados para compra</h2>
          <p className="m-0 font-label-sm text-label-sm font-normal text-on-surface-variant">Pedidos colocados y en camino</p>
        </div>
        {scheduled.map((p, i) => (
          <div key={i} className="flex items-center gap-3 rounded-2xl bg-white p-3 shadow-[0_1px_2px_rgba(51,27,17,.05)]">
            <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-surface-container text-secondary">
              <span aria-hidden="true" className="material-symbols-outlined text-[18px]">local_shipping</span>
            </div>
            <div className="min-w-0 flex-1">
              <span className="block font-body-md text-body-md font-semibold text-primary">{p.what}</span>
              <span className="font-label-sm text-label-sm font-normal text-on-surface-variant">{p.who} · {p.when}</span>
            </div>
            <span className={`flex-shrink-0 rounded-full px-2 py-0.5 font-label-sm text-label-sm font-semibold ${p.tone === "warn" ? "bg-[rgba(185,133,86,.18)] text-on-tertiary-fixed-variant" : "bg-surface-container-high text-on-surface-variant"}`}>{p.status}</span>
          </div>
        ))}
        {scheduled.length === 0 && <p className="m-0 rounded-2xl bg-surface-container p-4 text-center text-[13px] text-on-surface-variant">Sin pedidos en camino</p>}
        <button type="button" onClick={onGoDecisiones} className="flex min-h-[48px] items-center justify-center gap-2 rounded-full bg-surface-container-high font-body-md text-body-md font-medium text-primary">
          <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-secondary">fact_check</span>
          {pendingBuy > 0 ? `${pendingBuy} ${pendingBuy === 1 ? "compra espera" : "compras esperan"} tu decisión` : "Sin compras pendientes"}
        </button>
      </section>
    </main>
  );
}
