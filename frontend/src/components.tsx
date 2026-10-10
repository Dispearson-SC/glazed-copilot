import { useEffect, useState } from "react";
import { useApi } from "./ApiContext";
import { storeLabel } from "./types";
import type { Store } from "./types";

export function ErrorBox({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <div role="alert" className="error">
      {error.message}. Verifica que el backend esté corriendo.
    </div>
  );
}

/** Loads the store list and keeps the selected store id. */
export function useStores() {
  const api = useApi();
  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState<string>("");
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => {
    api
      .listStores()
      .then((s) => {
        setStores(s);
        setStoreId((cur) => cur || s[0]?.store_id || "");
      })
      .catch(setError);
  }, [api]);
  return { stores, storeId, setStoreId, error };
}

export function StoreSelect(props: { stores: Store[]; value: string; onChange: (id: string) => void }) {
  return (
    <label>
      Sucursal{" "}
      <select value={props.value} onChange={(e) => props.onChange(e.target.value)}>
        {props.stores.map((s) => (
          <option key={s.store_id} value={s.store_id}>
            {storeLabel(s)}
          </option>
        ))}
      </select>
    </label>
  );
}
