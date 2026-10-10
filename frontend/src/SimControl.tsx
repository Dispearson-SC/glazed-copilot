import { useEffect, useState } from "react";
import { useMatch } from "react-router-dom";
import { useApi } from "./ApiContext";
import { useSession } from "./SessionContext";
import { actionLabel } from "./issues";
import type { InjectBody, Proposal } from "./types";
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
  const [panel, setPanel] = useState<"exec" | "event" | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [proposalId, setProposalId] = useState("");
  const [detail, setDetail] = useState("");
  const [evType, setEvType] = useState("bloqueo");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

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

  async function inject(body: InjectBody) {
    if (!currentCase) return;
    setBusy(true);
    try {
      await api.inject(currentCase.case_id, body);
      setError(null);
      setPanel(null);
      session.bump();
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }

  async function openPanel(which: "exec" | "event") {
    setPanel(which);
    if (which === "exec" && currentCase) {
      try {
        setProposals((await api.listProposals({ case_id: currentCase.case_id, status: "approved" })) ?? []);
      } catch (e) {
        setError(e as Error);
      }
    }
  }

  return (
    <span className="sim">
      Fecha simulada: <strong>{simToday ?? currentCase.sim_today}</strong>{" "}
      <button onClick={() => void advance()} disabled={busy}>Avanzar 1 día</button>
      <button onClick={() => void openPanel("exec")} disabled={busy}>Inyectar no ejecutado</button>{" "}
      <button onClick={() => void openPanel("event")} disabled={busy}>Inyectar evento</button>
      {panel === "exec" && (
        <span className="inject">
          {" "}
          <label>
            Propuesta{" "}
            <select value={proposalId} onChange={(e) => setProposalId(e.target.value)}>
              <option value="">—</option>
              {proposals.map((p) => (
                <option key={p.proposal_id} value={p.proposal_id}>
                  {actionLabel(p.action_type)} ({p.proposal_id})
                </option>
              ))}
            </select>
          </label>{" "}
          <label>
            Detalle <input value={detail} onChange={(e) => setDetail(e.target.value)} />
          </label>{" "}
          <button
            disabled={!proposalId || busy}
            onClick={() =>
              void inject({
                execution: { proposal_id: proposalId, status: "not_executed", ...(detail.trim() ? { detail: detail.trim() } : {}) },
              })
            }
          >
            Confirmar no ejecutado
          </button>
        </span>
      )}
      {panel === "event" && (
        <span className="inject">
          {" "}
          <label>
            Tipo de evento{" "}
            <select value={evType} onChange={(e) => setEvType(e.target.value)}>
              <option value="bloqueo">bloqueo</option>
              <option value="clima_extremo">clima_extremo</option>
              <option value="evento_local">evento_local</option>
            </select>
          </label>{" "}
          <label>
            Desde <input value={from} onChange={(e) => setFrom(e.target.value)} placeholder="AAAA-MM-DD" />
          </label>{" "}
          <label>
            Hasta <input value={to} onChange={(e) => setTo(e.target.value)} placeholder="AAAA-MM-DD" />
          </label>{" "}
          <button
            disabled={!from || busy}
            onClick={() => void inject({ event: { type: evType, date_from: from, ...(to ? { date_to: to } : {}) } })}
          >
            Confirmar evento
          </button>
        </span>
      )}
      {error && <span role="alert" className="error"> {error.message}</span>}
    </span>
  );
}
