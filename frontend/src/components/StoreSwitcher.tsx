import { useEffect, useState, type ReactNode } from "react";
import { useApi } from "../ApiContext";
import { DEFAULT_SIM_TODAY } from "../config";
import { useSession } from "../SessionContext";
import { storeLabel, type Store } from "../types";

/** True when the store is closed (or not yet open) on the simulated date. Absent dates mean selectable. */
export const storeClosedReason = (s: Store, simToday: string = DEFAULT_SIM_TODAY): boolean =>
  Boolean((s.closed_on && s.closed_on <= simToday) || (s.opened_on && s.opened_on > simToday));

/** Tappable header area: opens a searchable store sheet and switches the whole session to the chosen store. */
export default function StoreSwitcher({ children, className = "" }: { children: ReactNode; className?: string }) {
  const api = useApi();
  const session = useSession();
  const { storeId, setStoreId, setCaseId, bump } = session;
  const [stores, setStores] = useState<Store[]>([]);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let alive = true;
    api
      .listStores()
      .then((s) => {
        if (!alive) return;
        setStores(s);
        // A persisted choice that is no longer in /stores is ignored.
        if (storeId && s.length > 0 && !s.some((x) => x.store_id === storeId)) setStoreId("");
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const current = storeId || stores[0]?.store_id || "";
  const q = query.trim().toLowerCase();
  const shown = stores.filter((s) => !q || [s.display_name, s.site_name, s.name].some((v) => v?.toLowerCase().includes(q)));

  const choose = (id: string) => {
    setOpen(false);
    setQuery("");
    if (id === current && id === storeId) return;
    setStoreId(id);
    setCaseId("");
    bump();
  };

  return (
    <>
      <button
        type="button"
        aria-label="Cambiar sucursal"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen(true)}
        className={`flex min-w-0 items-center gap-1 border-0 bg-transparent p-0 text-left ${className}`}
      >
        <span className="min-w-0 flex-1">{children}</span>
        <span aria-hidden="true" className="material-symbols-outlined flex-shrink-0 text-[18px] text-on-surface-variant">expand_more</span>
      </button>
      {open && (
        <div className="fixed inset-0 z-[60]">
          <div data-testid="store-backdrop" className="absolute inset-0 bg-black/30" onClick={() => setOpen(false)} />
          <div
            role="dialog"
            aria-label="Elegir sucursal"
            className="absolute inset-x-4 top-[calc(4rem+env(safe-area-inset-top))] mx-auto flex max-h-[70vh] max-w-[480px] flex-col rounded-[20px] border border-partition/60 bg-elevation p-3 shadow-card"
          >
            <h2 className="mb-2 px-1 font-headline-sm text-headline-sm text-primary" style={{ fontFamily: "'Playfair Display', serif" }}>
              Sucursales
            </h2>
            <input
              type="search"
              role="searchbox"
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar sucursal"
              aria-label="Buscar sucursal"
              className="mb-2 h-11 w-full rounded-[14px] border border-partition/60 bg-white px-3 font-body-md text-body-md"
            />
            <ul className="m-0 flex-1 list-none space-y-1 overflow-y-auto p-0">
              {shown.length === 0 && <li className="px-2 py-3 font-body-md text-body-md text-on-surface-variant">Sin resultados</li>}
              {shown.map((s) => {
                const closed = storeClosedReason(s);
                const isCurrent = s.store_id === current;
                const label = storeLabel(s);
                return (
                  <li key={s.store_id}>
                    <button
                      type="button"
                      disabled={closed}
                      aria-label={closed ? `${label}, Cerrada` : label}
                      aria-current={isCurrent ? "true" : undefined}
                      onClick={() => choose(s.store_id)}
                      className={`flex min-h-[44px] w-full items-center justify-between gap-2 rounded-[14px] border px-3 py-2 text-left font-body-md text-body-md disabled:opacity-50 ${
                        isCurrent ? "border-primary bg-white font-semibold text-primary" : "border-partition/40 bg-transparent text-on-surface"
                      }`}
                    >
                      <span className="min-w-0 flex-1 truncate">{label}</span>
                      {closed && <span className="flex-shrink-0 font-label-sm text-label-sm text-on-surface-variant">Cerrada</span>}
                      {isCurrent && !closed && <span aria-hidden="true" className="material-symbols-outlined text-[18px]">check</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}
