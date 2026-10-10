import { useState } from "react";
import { filterMemories, SOON_TEXT, type Memory } from "../../data/copilot";
import type { MemoryState } from "../../useMemoryData";

export const MEMORY_FILTERS = [
  ["todas", "Todas"],
  ["proveedores", "Proveedores"],
  ["demanda", "Demanda"],
  ["eventos", "Eventos"],
  ["preferencias", "Preferencias"],
] as const;

export function FilterChips({ options, value, onChange }: { options: readonly (readonly [string, string])[]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex gap-2 overflow-x-auto">
      {options.map(([id, label]) => (
        <button
          key={id}
          type="button"
          aria-pressed={value === id}
          onClick={() => onChange(id)}
          className={`min-h-[44px] flex-shrink-0 rounded-full px-3.5 text-[13px] font-medium leading-[18px] ${value === id ? "bg-primary-container text-surface" : "bg-partition text-primary"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

/** Memorias window: search, category filters and what the copilot knows about the branch. */
export default function MemoriesWindow({
  storeCode,
  memories,
  filter,
  onFilter,
  state,
}: {
  storeCode: string;
  memories: Memory[];
  filter: string;
  onFilter: (f: string) => void;
  state: MemoryState;
}) {
  const [query, setQuery] = useState("");
  const shown = filterMemories(memories, filter, query);
  return (
    <main className="mx-auto flex w-full max-w-[640px] flex-col gap-4 px-4 pb-28 pt-[68px]">
      <header className="flex flex-col gap-1 pt-3">
        <span className="font-label-md text-label-md uppercase tracking-[0.05em] text-on-tertiary-container">Poco a poco · {storeCode}</span>
        <h1 className="m-0 font-headline-lg text-headline-lg tracking-tight text-primary">Memorias técnicas</h1>
        <p className="m-0 font-body-md text-body-md text-on-surface-variant">Lo que el copiloto sabe de tu sucursal. Cada cifra se verifica contra el registro de decisiones.</p>
      </header>
      <label className="flex items-center gap-2 rounded-full border border-surface-container-high bg-white px-4 py-3">
        <span aria-hidden="true" className="material-symbols-outlined text-[20px] text-secondary">search</span>
        <span className="sr-only">Buscar una memoria</span>
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Busca una memoria" className="min-w-0 flex-1 border-0 bg-transparent p-0 font-body-md text-body-md text-on-surface outline-none" />
      </label>
      <FilterChips options={MEMORY_FILTERS} value={filter} onChange={onFilter} />
      <div className="flex flex-col">
        {shown.map((m) => (
          <article key={m.id} className="flex flex-col gap-1.5 border-b border-partition/70 px-1 py-3.5">
            <div className="flex items-center justify-between gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-surface-container px-2 py-0.5 font-label-sm text-label-sm font-semibold text-secondary">
                <span aria-hidden="true" className="material-symbols-outlined text-[14px]">{m.icon}</span>
                {m.tag}
              </span>
              {m.isNew && <span className="rounded-full bg-on-tertiary-container px-2 py-0.5 font-label-sm text-label-sm font-semibold text-white">Nuevo aprendizaje</span>}
            </div>
            <p className="m-0 font-headline-sm text-[17px] font-medium leading-6 text-primary">{m.text}</p>
            <div className="flex items-center justify-between gap-2 font-label-sm text-label-sm font-normal text-on-surface-variant">
              <span>{m.src}</span>
              <span className="flex-shrink-0 font-semibold">{m.conf}</span>
            </div>
          </article>
        ))}
        {shown.length === 0 && <p className="m-0 py-6 text-center text-[13px] text-on-surface-variant">{state === "loading" ? "Cargando memorias…" : state === "soon" ? SOON_TEXT : state === "error" ? "No se pudieron cargar las memorias." : memories.length === 0 ? "Aún no hay memorias. Se irán sumando con tus decisiones." : "Sin memorias que coincidan"}</p>}
      </div>
      <p className="m-0 text-[12px] leading-[18px] text-on-surface-variant">Las memorias se escriben solo después de una decisión o de un resultado medido. Con un solo caso, el copiloto lo dice y la confianza queda baja.</p>
    </main>
  );
}
