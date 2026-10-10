import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApi } from "../ApiContext";
import { ErrorBox, useStores } from "../components";
import { DEFAULT_SIM_TODAY } from "../config";
import { useSession } from "../SessionContext";
import type { Case } from "../types";
import { storeLabel } from "../types";
import { pickCase } from "../useCurrentCase";

const field =
  "w-full rounded-full border border-surface-container bg-surface px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:border-secondary focus:ring-2 focus:ring-on-tertiary-container/40";

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
    <div className="flex flex-col w-full max-w-[480px] mx-auto gap-space-md">
      <section className="relative overflow-hidden rounded-[20px] bg-primary-container text-surface-container-lowest p-space-lg shadow-xl shadow-primary-container/20">
        <div className="absolute -right-12 -top-12 w-48 h-48 rounded-full bg-secondary-container/10 blur-2xl pointer-events-none"></div>
        <div className="relative z-10 flex flex-col gap-space-sm">
          <img alt="Glazed" className="h-12 w-auto object-contain self-start" src="/Logo-Full.png" />
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
          <label className="flex flex-col gap-1.5 font-label-md text-label-md text-on-surface">
            Sucursal
            <select className={field} value={current} onChange={(e) => setStoreId(e.target.value)}>
              {stores.map((s) => (
                <option key={s.store_id} value={s.store_id}>
                  {storeLabel(s)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 font-label-md text-label-md text-on-surface">
            Caso
            <select className={field} value={caseId} onChange={(e) => setCaseId(e.target.value)}>
              {cases.length === 0 && <option value="">Sin casos (se usará el caso activo)</option>}
              {cases.map((c) => (
                <option key={c.case_id} value={c.case_id}>
                  {c.title || c.case_id}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={!current}
            className="w-full py-3.5 px-space-md bg-secondary text-surface-container-lowest font-body-md text-body-md font-semibold rounded-full flex items-center justify-center gap-2 shadow-md shadow-secondary/20 hover:bg-primary transition-all active:scale-[0.98] disabled:opacity-60"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">login</span>
            Entrar
          </button>
        </form>
      </section>
    </div>
  );
}
