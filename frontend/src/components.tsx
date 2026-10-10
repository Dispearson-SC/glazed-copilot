import { useEffect, useState } from "react";
import { useApi } from "./ApiContext";
import type { Store } from "./types";

export function ErrorBox({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <div role="alert" className="rounded-[14px] bg-error-container text-on-error-container px-4 py-2.5 font-body-md text-body-md">
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
