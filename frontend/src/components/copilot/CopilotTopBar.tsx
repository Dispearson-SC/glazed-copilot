import { Link } from "react-router-dom";

/** Fixed 64px top bar: logo, brand, store code and the settings button. */
export default function CopilotTopBar({ storeCode, onSettings }: { storeCode: string; onSettings: () => void }) {
  return (
    <header className="fixed inset-x-0 top-0 z-40 bg-surface/[.88] pt-safe backdrop-blur-xl shadow-[0_1px_8px_rgba(75,48,37,.04)]">
      <div className="mx-auto flex h-16 max-w-[640px] items-center justify-between px-4">
        <Link to="/" aria-label="Volver al resumen" className="flex min-w-0 items-center gap-2 no-underline">
          <img alt="Logo Glazed Co." src="/Logo.png" className="h-8 w-8 rounded-full object-contain" />
          <div className="flex min-w-0 flex-col">
            <span className="font-headline-sm text-headline-sm tracking-tight text-primary">Glazed Co.</span>
            <span className="flex items-center gap-1 truncate font-label-sm text-label-sm font-normal text-on-surface-variant">
              <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-on-tertiary-container" />
              <span className="truncate">Copiloto · Sucursal {storeCode}</span>
            </span>
          </div>
        </Link>
        <button
          type="button"
          onClick={onSettings}
          aria-label="Ajustes del copiloto"
          className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full border border-partition/60 bg-white p-0 text-secondary shadow-card"
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[22px]">tune</span>
        </button>
      </div>
    </header>
  );
}
