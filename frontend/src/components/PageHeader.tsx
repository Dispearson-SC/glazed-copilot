import { longDate } from "../format";

export default function PageHeader({ date, simToday }: { date: string; simToday: string }) {
  return (
    <header className="flex flex-col gap-space-xs pt-space-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-space-xs">
          <span className="inline-flex items-center justify-center w-2 h-2 rounded-full bg-on-tertiary-container animate-ping"></span>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container-high text-on-tertiary-container font-label-sm text-label-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-on-tertiary-container"></span>
            Fecha simulada
          </span>
        </div>
        <span className="font-label-sm text-label-sm text-on-surface-variant flex items-center gap-1">
          <span aria-hidden="true" className="material-symbols-outlined text-[14px]">schedule</span>
          <span data-testid="sim-today">{simToday}</span>
        </span>
      </div>
      <div className="flex flex-col mt-1">
        <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">Resumen de hoy</h1>
        <p className="font-body-md text-body-md text-on-surface-variant capitalize">{longDate(date)}</p>
      </div>
    </header>
  );
}
