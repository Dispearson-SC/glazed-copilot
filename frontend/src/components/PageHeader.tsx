import type { CaseMode } from "../types";

const MODE_LABEL: Record<CaseMode, string> = { live: "En vivo", sandbox: "Simulación", backtest: "Prueba histórica" };

const weekdayLong = (iso: string) => new Intl.DateTimeFormat("es-MX", { weekday: "long", timeZone: "UTC" }).format(new Date(`${iso.slice(0, 10)}T00:00:00Z`));
const monthLong = (iso: string) => new Intl.DateTimeFormat("es-MX", { month: "long", timeZone: "UTC" }).format(new Date(`${iso.slice(0, 10)}T00:00:00Z`));
const cap = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

/** "Jueves, 24 De Octubre 2024" (Main.dc.html capitalises every word). */
export const mainDate = (iso: string): string => `${cap(weekdayLong(iso))}, ${Number(iso.slice(8, 10))} De ${cap(monthLong(iso))} ${iso.slice(0, 4)}`;

/** Live badge, clock, title and date. The backend has no shift or time of day, so those parts say "Sin datos". */
export default function PageHeader({ date, mode }: { date: string; mode: CaseMode }) {
  return (
    <header className="flex flex-col gap-space-xs pt-space-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-space-xs">
          <span className="inline-flex items-center justify-center w-2 h-2 rounded-full bg-on-tertiary-container animate-ping"></span>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container-high text-on-tertiary-container font-label-sm text-label-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-on-tertiary-container"></span>
            {MODE_LABEL[mode]} • Sin datos
          </span>
        </div>
        <span className="font-label-sm text-label-sm text-on-surface-variant flex items-center gap-1">
          <span aria-hidden="true" className="material-symbols-outlined text-[14px]">schedule</span>
          <span data-testid="sim-clock">Sin datos</span>
        </span>
      </div>
      <div className="flex flex-col mt-1">
        <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">Resumen de hoy</h1>
        <p className="font-body-md text-body-md text-on-surface-variant">{mainDate(date)}</p>
      </div>
    </header>
  );
}
