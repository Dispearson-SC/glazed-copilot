import { useEffect, useState } from "react";

export const REJECT_REASONS = ["Precio o costo", "Desconfío del dato", "Falta personal", "Mal momento", "Prefiero no quedarme corto", "Otro"];

/** Bottom sheet asking why a decision is rejected. A chip or free text is required. */
export default function RejectSheet({
  title,
  busy,
  onCancel,
  onSubmit,
}: {
  title: string;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (r: { label: string; text: string }) => void;
}) {
  const [label, setLabel] = useState<string | null>(null);
  const [text, setText] = useState("");
  const cant = !label && !text.trim();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCancel();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div className="fixed inset-0 z-[80]">
      <button type="button" aria-label="Cerrar" onClick={onCancel} className="absolute inset-0 h-full w-full border-0 bg-primary-container/40 p-0" />
      <section
        role="dialog"
        aria-label="Motivo del rechazo"
        className="absolute inset-x-0 bottom-0 mx-auto flex max-w-[640px] flex-col gap-3.5 rounded-t-3xl bg-elevation px-5 pb-7 pt-3 shadow-sheet"
      >
        <div aria-hidden="true" className="h-1 w-10 self-center rounded-full bg-partition" />
        <div>
          <span className="font-label-md text-label-md uppercase tracking-[0.05em] text-on-tertiary-container">Rechazar decisión</span>
          <h2 className="m-0 mt-1 font-headline-md text-headline-md font-semibold text-primary">¿Por qué la rechazas?</h2>
          <p className="m-0 mt-1 text-[13px] leading-[19px] text-on-surface-variant">{title}. Tu motivo entrena al copiloto para las próximas propuestas.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {REJECT_REASONS.map((r) => (
            <button
              key={r}
              type="button"
              aria-pressed={label === r}
              onClick={() => setLabel(label === r ? null : r)}
              className={`min-h-[44px] rounded-full px-3.5 text-[13px] font-medium leading-[18px] ${label === r ? "bg-primary-container text-surface" : "bg-partition text-primary"}`}
            >
              {r}
            </button>
          ))}
        </div>
        <label htmlFor="reject-text" className="font-label-md text-label-md text-on-surface">Cuéntale más (opcional)</label>
        <textarea
          id="reject-text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          placeholder="Ej. El lunes hay evento en la terminal y prefiero tener más producto."
          className="-mt-2 resize-none rounded-2xl border border-partition bg-white px-3.5 py-3 font-body-md text-body-md text-on-surface outline-none"
        />
        <button
          type="button"
          disabled={cant || busy}
          onClick={() => onSubmit({ label: label ?? "", text: text.trim() })}
          className="flex min-h-[52px] items-center justify-center gap-2 rounded-full bg-secondary font-body-md text-body-md font-semibold text-white shadow-[0_4px_6px_-1px_rgba(122,86,73,.2)] disabled:opacity-[.45]"
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[20px]">school</span>
          Enviar motivo y rechazar
        </button>
      </section>
    </div>
  );
}
