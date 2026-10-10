import { useEffect, useState } from "react";
import { useApi } from "./ApiContext";
import type { Store } from "./types";

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
