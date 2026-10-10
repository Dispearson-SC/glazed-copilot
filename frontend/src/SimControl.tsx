import { useEffect, useState } from "react";
import { useMatch } from "react-router-dom";
import { useApi } from "./ApiContext";
import { useSession } from "./SessionContext";
import { useCurrentCase } from "./useCurrentCase";

export default function SimControl() {
  const api = useApi();
  const session = useSession();
  const match = useMatch("/stores/:storeId/*");
  const [firstStore, setFirstStore] = useState("");
  useEffect(() => {
    api.listStores().then((s) => setFirstStore(s[0]?.store_id ?? "")).catch(() => {});
  }, [api]);
  const storeId = match?.params.storeId ?? (session.storeId || firstStore);
  const { currentCase, loading } = useCurrentCase(storeId);
  const [simToday, setSimToday] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => setSimToday(null), [currentCase?.case_id]);

  if (!currentCase) return <span className="sim">{loading ? "…" : "Sin caso activo"}</span>;

  async function advance() {
    if (!currentCase) return;
    setBusy(true);
    try {
      const res = await api.advance(currentCase.case_id, 1);
      setSimToday(res.sim_today);
      setError(null);
      session.bump();
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="sim">
      Fecha simulada: <strong>{simToday ?? currentCase.sim_today}</strong>{" "}
      <button onClick={() => void advance()} disabled={busy}>Avanzar 1 día</button>
      {error && <span role="alert" className="error"> {error.message}</span>}
    </span>
  );
}
