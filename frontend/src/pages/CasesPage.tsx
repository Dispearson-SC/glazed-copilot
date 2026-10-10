import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../ApiContext";
import { ErrorBox, StoreSelect, useStores } from "../components";
import type { CaseMode, Turn } from "../types";
import { usePolling } from "../usePolling";

const TURN_POLL_MS = 1500;

function AskBox({ storeId, caseId }: { storeId: string; caseId: string }) {
  const api = useApi();
  const [text, setText] = useState("");
  const [turnId, setTurnId] = useState<string | null>(null);
  const [turn, setTurn] = useState<Turn | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const waiting = turnId !== null && (turn === null || turn.status === "pending");

  usePolling(
    async () => {
      if (!turnId) return null;
      const t = await api.getTurn(caseId, turnId);
      setTurn(t);
      return t;
    },
    TURN_POLL_MS,
    waiting,
    [turnId],
  );

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim() || !caseId) return;
    setError(null);
    setTurn(null);
    try {
      const { turn_id } = await api.sendMessage(caseId, text.trim());
      setTurnId(turn_id);
    } catch (err) {
      setError(err as Error);
    }
  }

  return (
    <form onSubmit={submit} className="card">
      <h3>Preguntar al caso {caseId}</h3>
      <label>
        Pregunta <input value={text} onChange={(e) => setText(e.target.value)} size={50} />
      </label>{" "}
      <button type="submit" disabled={!caseId}>Preguntar</button>
      <ErrorBox error={error} />
      {waiting && <p className="muted">Esperando respuesta…</p>}
      {turn?.status === "done" && <p className="reply">{turn.reply}</p>}
      {turn?.status === "failed" && <div role="alert" className="error">Falló el turno: {turn.error}</div>}
      {turn?.status === "waiting_approval" && <p className="muted">Hay una propuesta esperando aprobación.</p>}
      {turnId && (
        <Link to={`/stores/${storeId}/trace?case=${caseId}&turn=${turnId}`}>Ver traza</Link>
      )}
    </form>
  );
}

export default function CasesPage() {
  const api = useApi();
  const { stores, storeId, setStoreId, error: storesError } = useStores();
  const cases = usePolling(() => (storeId ? api.listCases({ store_id: storeId }) : Promise.resolve([])), 30_000, false, [
    storeId,
  ]);
  const [simToday, setSimToday] = useState("");
  const [mode, setMode] = useState<CaseMode>("live");
  const [title, setTitle] = useState("");
  const [askCase, setAskCase] = useState("");
  const [actionError, setActionError] = useState<Error | null>(null);
  const error = storesError ?? cases.error ?? actionError;
  const selectedCase = askCase || cases.data?.[0]?.case_id || "";

  async function run(action: () => Promise<unknown>) {
    setActionError(null);
    try {
      await action();
      await cases.refresh();
    } catch (e) {
      setActionError(e as Error);
    }
  }

  function create(e: FormEvent) {
    e.preventDefault();
    void run(() =>
      api.createCase({ store_id: storeId, sim_today: simToday, mode, ...(title ? { title } : {}) }),
    );
  }

  return (
    <section>
      <h2>Casos</h2>
      <StoreSelect stores={stores} value={storeId} onChange={setStoreId} />
      <ErrorBox error={error} />

      <form onSubmit={create} className="card">
        <h3>Nuevo caso</h3>
        <label>Fecha simulada <input type="date" value={simToday} onChange={(e) => setSimToday(e.target.value)} required /></label>{" "}
        <label>
          Modo{" "}
          <select value={mode} onChange={(e) => setMode(e.target.value as CaseMode)}>
            <option value="live">live</option>
            <option value="sandbox">sandbox</option>
            <option value="backtest">backtest</option>
          </select>
        </label>{" "}
        <label>Título <input value={title} onChange={(e) => setTitle(e.target.value)} /></label>{" "}
        <button type="submit">Crear caso</button>
      </form>

      {!error && cases.data?.length === 0 && <p className="muted">Sin casos</p>}
      <ul className="cases">
        {cases.data?.map((c) => (
          <li key={c.case_id}>
            <strong>{c.title}</strong> <span className="badge">{c.mode}</span> {c.sim_today}{" "}
            <code>{c.case_id}</code>
            {c.parent_case_id && <small> (fork de {c.parent_case_id})</small>}{" "}
            <button onClick={() => void run(() => api.forkCase(c.case_id, {}))}>Bifurcar</button>{" "}
            <button onClick={() => setAskCase(c.case_id)}>Usar para preguntar</button>{" "}
            <Link to={`/stores/${c.store_id}/trace?case=${c.case_id}`}>Traza</Link>
          </li>
        ))}
      </ul>

      {selectedCase && <AskBox key={selectedCase} storeId={storeId} caseId={selectedCase} />}
    </section>
  );
}
