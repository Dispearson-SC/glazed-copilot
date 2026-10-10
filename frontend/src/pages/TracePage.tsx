import CentinelaPanel from "../CentinelaPanel";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useApi } from "../ApiContext";
import { ErrorBox, useStores } from "../components";
import { AGENTS, groupByLane, sortByTs, summarizePayload } from "../trace";
import { storeLabel } from "../types";
import type { Case, TraceEvent, TurnStatus } from "../types";
import { usePolling } from "../usePolling";

const POLL_MS = 3000;

function Bubble({ event, index }: { event: TraceEvent; index: number }) {
  const [open, setOpen] = useState(false);
  const fromOrch = event.from_agent === "orchestrator" || event.to_agent === "orchestrator";
  return (
    <li data-testid={`bubble-${index}`} className={`bubble ${event.kind} ${fromOrch ? "orchestrator" : ""}`}>
      <div className="meta">
        <strong>{event.from_agent}</strong> → <strong>{event.to_agent}</strong>{" "}
        <span className="badge">{event.kind}</span>{" "}
        <time>{new Date(event.ts).toLocaleTimeString()}</time>
      </div>
      <div>{summarizePayload(event.payload)}</div>
      <button onClick={() => setOpen((o) => !o)}>{open ? "Ocultar payload" : "Ver payload"}</button>
      {open && <pre>{JSON.stringify(event.payload, null, 2)}</pre>}
    </li>
  );
}

function Lanes({ events }: { events: TraceEvent[] }) {
  const lanes = groupByLane(events);
  return (
    <div className="lanes">
      {AGENTS.map((agent) => (
        <div key={agent} data-testid={`lane-${agent}`} className={`lane ${agent === "orchestrator" ? "orchestrator" : ""}`}>
          <h4>{agent}</h4>
          {lanes[agent].map((e, i) => (
            <div key={i} data-testid={`lane-item-${agent}-${i}`} className={`lane-item ${e.kind}`}>
              <small>{e.from_agent === agent ? `→ ${e.to_agent}` : `← ${e.from_agent}`}</small>
              <div>{e.kind}</div>
              <small>{summarizePayload(e.payload, 40)}</small>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

export default function TracePage() {
  const api = useApi();
  const { storeId = "" } = useParams();
  const { stores } = useStores();
  const found = stores.find((s) => s.store_id === storeId);
  const storeName = found ? storeLabel(found) : "…";
  const [params, setParams] = useSearchParams();
  const turnId = params.get("turn");
  const [cases, setCases] = useState<Case[]>([]);
  const [casesError, setCasesError] = useState<Error | null>(null);
  const [caseId, setCaseId] = useState(params.get("case") ?? "");
  const [turnStatus, setTurnStatus] = useState<TurnStatus | null>(null);

  useEffect(() => {
    api
      .listCases({ store_id: storeId })
      .then((cs) => {
        setCases(cs);
        setCaseId((cur) => cur || cs[0]?.case_id || "");
      })
      .catch(setCasesError);
  }, [api, storeId]);

  const turnPending = Boolean(turnId) && (turnStatus === null || turnStatus === "pending");

  usePolling(
    async () => {
      if (!turnId || !caseId) return null;
      const t = await api.getTurn(caseId, turnId);
      setTurnStatus(t.status);
      return t;
    },
    POLL_MS,
    turnPending && Boolean(caseId),
    [caseId, turnId],
  );

  const trace = usePolling(
    () => (caseId ? api.getTrace(storeId, caseId) : Promise.resolve([])),
    POLL_MS,
    turnPending,
    [storeId, caseId],
  );

  // One last load when the turn leaves "pending" so the final events show up.
  const { refresh } = trace;
  useEffect(() => {
    if (turnStatus && turnStatus !== "pending") void refresh();
  }, [turnStatus, refresh]);

  const events = sortByTs(trace.data ?? []);
  const error = casesError ?? trace.error;

  return (
    <section>
      <h2>Inspector de agentes - {storeName}</h2>
      <label>
        Caso{" "}
        <select
          value={caseId}
          onChange={(e) => {
            setCaseId(e.target.value);
            setTurnStatus(null);
            setParams({ case: e.target.value });
          }}
        >
          {cases.map((c) => (
            <option key={c.case_id} value={c.case_id}>
              {c.title} ({c.case_id})
            </option>
          ))}
        </select>
      </label>{" "}
      <button onClick={() => void trace.refresh()}>Actualizar</button>
      {turnId && (
        <span className="muted">
          {" "}
          {turnPending ? "Turno en curso, actualizando cada 3 s…" : `Turno terminado (${turnStatus})`}
        </span>
      )}
      <ErrorBox error={error} />
      {!error && !trace.loading && events.length === 0 && <p className="muted">Sin eventos todavía</p>}
      {events.length > 0 && (
        <>
          <h3>Canal conversacional</h3>
          <ol className="timeline">
            {events.map((e, i) => (
              <Bubble key={e.event_id ?? i} event={e} index={i} />
            ))}
          </ol>
          <h3>Carriles por agente</h3>
          <Lanes events={events} />
        </>
      )}
      {caseId && <CentinelaPanel caseId={caseId} />}
    </section>
  );
}
