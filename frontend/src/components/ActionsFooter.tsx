/** Report, close-shift and sync line of Main.dc.html. The backend has no report or shift-close route yet, so both buttons are disabled. */
export default function ActionsFooter({ minutesAgo }: { minutesAgo: number | null }) {
  return (
    <section className="flex flex-col items-center gap-space-sm pt-space-xs pb-space-md">
      <div className="w-full flex flex-col gap-2">
        <button
          type="button"
          disabled
          title="Disponible pronto"
          className="w-full py-3.5 px-space-md bg-secondary text-surface-container-lowest font-body-md text-body-md font-semibold rounded-full flex items-center justify-center gap-2 shadow-md shadow-secondary/20 disabled:opacity-40"
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[20px]">download</span>
          Descargar reporte del día (PDF)
        </button>
        <button
          type="button"
          disabled
          title="Disponible pronto"
          className="w-full py-3 px-space-md bg-surface-container-high text-primary font-body-md text-body-md font-medium rounded-full flex items-center justify-center gap-2 disabled:opacity-40"
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-secondary">lock_clock</span>
          Cerrar turno de caja
        </button>
      </div>
      <div className="flex items-center gap-1.5 text-on-surface-variant font-label-sm text-label-sm mt-1">
        <span aria-hidden="true" className="material-symbols-outlined text-[14px]">sync</span>
        <span>{minutesAgo == null ? "Última sincronización automática: Sin datos" : `Última sincronización automática hace ${minutesAgo} min`}</span>
      </div>
    </section>
  );
}
