import { useState } from "react";
import { useApi } from "../../ApiContext";
import { isUnavailable } from "../../api";
import type { NoteBody } from "../../types";

const CATEGORIES: { id: NoteBody["category"]; label: string }[] = [
  { id: "eventos", label: "Eventos" },
  { id: "demanda", label: "Demanda" },
  { id: "proveedores", label: "Proveedores" },
  { id: "preferencias", label: "Preferencias" },
];

const field = "h-11 w-full rounded-[14px] border border-partition/60 bg-white px-3 font-body-md text-body-md text-on-surface";
const label = "flex flex-col gap-1 font-label-md text-label-md normal-case tracking-normal text-on-surface-variant";

/** Bottom sheet to write a manager note ("Anotar"); the backend turns it into a memory. */
export default function NoteSheet({ caseId, onClose, onSaved }: { caseId: string; onClose: () => void; onSaved: () => void }) {
  const api = useApi();
  const [text, setText] = useState("");
  const [category, setCategory] = useState<NoteBody["category"]>("eventos");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [impact, setImpact] = useState("");
  const [busy, setBusy] = useState(false);
  const [soon, setSoon] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!text.trim() || busy) return;
    setBusy(true);
    setSoon(false);
    setError(null);
    try {
      await api.addNote(caseId, {
        text: text.trim(),
        category,
        ...(dateFrom ? { date_from: dateFrom } : {}),
        ...(dateTo ? { date_to: dateTo } : {}),
        ...(impact.trim() ? { impact: impact.trim() } : {}),
      });
      onSaved();
    } catch (e) {
      if (isUnavailable(e)) setSoon(true);
      else setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60]">
      <div data-testid="note-backdrop" className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div role="dialog" aria-label="Anotar una nota" className="absolute inset-x-0 bottom-0 mx-auto flex max-h-[90vh] max-w-[640px] flex-col gap-3 overflow-y-auto rounded-t-[24px] border border-partition/60 bg-elevation p-4 shadow-card">
        <div className="flex items-center justify-between">
          <h2 className="m-0 font-headline-sm text-headline-sm text-primary" style={{ fontFamily: "'Playfair Display', serif" }}>Anotar</h2>
          <button type="button" aria-label="Cerrar" onClick={onClose} className="flex h-11 w-11 items-center justify-center rounded-full bg-transparent p-0 text-on-surface-variant">
            <span aria-hidden="true" className="material-symbols-outlined text-[22px]">close</span>
          </button>
        </div>
        <label className={label}>
          Nota
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} placeholder="Algo que el copiloto debería recordar" className="w-full resize-none rounded-[14px] border border-partition/60 bg-white p-3 font-body-md text-body-md text-on-surface" />
        </label>
        <div role="group" aria-label="Categoría" className="flex flex-wrap gap-2">
          {CATEGORIES.map((c) => (
            <button
              key={c.id}
              type="button"
              aria-pressed={category === c.id}
              onClick={() => setCategory(c.id)}
              className={`min-h-[44px] rounded-full px-4 font-label-md text-label-md normal-case tracking-normal ${category === c.id ? "bg-primary-container text-surface" : "bg-surface-container text-secondary"}`}
            >
              {c.label}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <label className={label}>
            Desde (opcional)
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className={field} />
          </label>
          <label className={label}>
            Hasta (opcional)
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className={field} />
          </label>
        </div>
        <label className={label}>
          Impacto esperado (opcional)
          <input type="text" value={impact} onChange={(e) => setImpact(e.target.value)} placeholder="Ej. -30% de afluencia" className={field} />
        </label>
        {soon && <p className="m-0 text-center text-[13px] text-on-surface-variant">Disponible pronto</p>}
        {error && <p role="alert" className="m-0 rounded-[14px] bg-error-container px-3 py-2 text-[13px] text-on-error-container">{error}</p>}
        <button
          type="button"
          disabled={!text.trim() || busy}
          onClick={() => void submit()}
          className="min-h-[48px] w-full rounded-full bg-primary-container font-body-md text-body-md font-semibold text-surface shadow-hero disabled:opacity-40"
        >
          Guardar nota
        </button>
      </div>
    </div>
  );
}
