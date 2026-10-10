import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApi } from "../ApiContext";
import PageShell from "../components/PageShell";
import { ErrorBox, useStores } from "../components";
import { DEFAULT_SIM_TODAY } from "../config";
import { useSession } from "../SessionContext";
import type { Case } from "../types";
import { storeLabel } from "../types";
import { pickCase } from "../useCurrentCase";

const pill =
  "flex items-center gap-2 rounded-full border border-surface-container bg-surface px-4 py-3 focus-within:border-secondary focus-within:ring-2 focus-within:ring-on-tertiary-container/40";
const control = "flex-1 min-w-0 bg-transparent outline-none font-body-md text-body-md text-on-surface";

/** Store and case picker. No credentials: real access control is the reverse proxy's basic auth. */
export default function LoginPage() {
  const api = useApi();
  const navigate = useNavigate();
  const session = useSession();
  const { stores, storeId: firstId, error: storesError } = useStores();
  const [storeId, setStoreId] = useState("");
  const [caseId, setCaseId] = useState("");
  const [cases, setCases] = useState<Case[]>([]);
  const [casesError, setCasesError] = useState<Error | null>(null);
  const current = storeId || session.storeId || firstId;

  useEffect(() => {
    if (!current) return;
    let live = true;
    api
      .listCases({ store_id: current })
      .then((c) => {
        if (!live) return;
        setCases(c);
        setCaseId((cur) => (c.some((x) => x.case_id === cur) ? cur : pickCase(c, "", DEFAULT_SIM_TODAY)?.case_id ?? ""));
        setCasesError(null);
      })
      .catch((e: Error) => live && setCasesError(e));
    return () => {
      live = false;
    };
  }, [api, current]);

  function enter() {
    session.setStoreId(current);
    session.setCaseId(caseId);
    navigate("/");
  }

  return (
    <PageShell subtitle="Sucursal" columnClass="flex flex-col w-full max-w-[480px] mx-auto gap-space-md pt-space-xs">
      <section className="relative overflow-hidden rounded-[20px] bg-primary-container text-surface-container-lowest p-space-lg shadow-xl shadow-primary-container/20">
        <div className="absolute -right-12 -top-12 w-48 h-48 rounded-full bg-secondary-container/10 blur-2xl pointer-events-none"></div>
        <div className="absolute -left-12 -bottom-12 w-40 h-40 rounded-full bg-on-tertiary-container/10 blur-2xl pointer-events-none"></div>
        <div className="relative z-10 flex flex-col gap-space-sm">
          <div className="w-9 h-9 rounded-full bg-surface-container-lowest/10 flex items-center justify-center text-tertiary-fixed-dim">
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">coffee_maker</span>
          </div>
          <h1 className="font-headline-lg text-headline-lg tracking-tight">Elige tu sucursal</h1>
          <p className="font-body-md text-body-md text-surface-variant">
            Selecciona la sucursal y el caso con el que quieres trabajar.
          </p>
        </div>
      </section>
      <section className="bg-surface-container-lowest rounded-[18px] p-space-lg shadow-sm shadow-primary/5 border border-surface-container">
        <ErrorBox error={storesError ?? casesError} />
        <form
          className="flex flex-col gap-space-md"
          onSubmit={(e) => {
            e.preventDefault();
            enter();
          }}
        >
          <div className="flex flex-col gap-1.5">
            <label htmlFor="login-store" className="font-label-md text-label-md text-on-surface">Sucursal</label>
            <div className={pill}>
              <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-secondary">storefront</span>
              <select id="login-store" className={control} value={current} onChange={(e) => setStoreId(e.target.value)}>
                {stores.map((s) => (
                  <option key={s.store_id} value={s.store_id}>
                    {storeLabel(s)}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="login-case" className="font-label-md text-label-md text-on-surface">Caso</label>
            <div className={pill}>
              <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-secondary">folder_open</span>
              <select id="login-case" className={control} value={caseId} onChange={(e) => setCaseId(e.target.value)}>
                {cases.length === 0 && <option value="">Sin casos (se usará el caso activo)</option>}
                {cases.map((c) => (
                  <option key={c.case_id} value={c.case_id}>
                    {c.title || c.case_id}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <button
            type="submit"
            disabled={!current}
            className="w-full py-3.5 px-space-md bg-secondary text-surface-container-lowest font-body-md text-body-md font-semibold rounded-full flex items-center justify-center gap-2 shadow-md shadow-secondary/20 hover:bg-primary transition-all active:scale-[0.98] disabled:opacity-60"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">login</span>
            Entrar al resumen
          </button>
        </form>
        <div className="my-space-md border-t border-surface-container"></div>
        <Link
          to="/"
          className="w-full py-3 px-space-md bg-surface-container-high text-primary font-body-md text-body-md font-medium rounded-full flex items-center justify-center gap-2 hover:bg-surface-variant transition-all active:scale-[0.98]"
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-secondary">arrow_back</span>
          Volver al resumen
        </Link>
      </section>
      <p className="text-center font-label-sm text-label-sm text-on-surface-variant">
        Sin credenciales: el acceso lo controla el proxy de la organización.
      </p>
    </PageShell>
  );
}
