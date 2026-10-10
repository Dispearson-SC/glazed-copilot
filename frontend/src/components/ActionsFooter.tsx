import { Link } from "react-router-dom";

export default function ActionsFooter({ asOf }: { asOf?: string }) {
  return (
    <section className="flex flex-col items-center gap-space-sm pt-space-xs pb-space-md">
      <div className="w-full flex flex-col gap-2">
        <Link
          to="/chat"
          className="w-full py-3.5 px-space-md bg-secondary text-surface-container-lowest font-body-md text-body-md font-semibold rounded-full flex items-center justify-center gap-2 shadow-md shadow-secondary/20 hover:bg-primary transition-all active:scale-[0.98]"
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[20px]">chat</span>
          Preguntar al asistente
        </Link>
        <Link
          to="/login"
          className="w-full py-3 px-space-md bg-surface-container-high text-primary font-body-md text-body-md font-medium rounded-full flex items-center justify-center gap-2 hover:bg-surface-variant transition-all active:scale-[0.98]"
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-secondary">storefront</span>
          Cambiar de sucursal
        </Link>
      </div>
      {asOf && (
        <div className="flex items-center gap-1.5 text-on-surface-variant font-label-sm text-label-sm mt-1">
          <span aria-hidden="true" className="material-symbols-outlined text-[14px]">sync</span>
          <span>Datos al {asOf}</span>
        </div>
      )}
    </section>
  );
}
