import { useApi } from "./ApiContext";
import { actionLabel, usd } from "./issues";
import type { ComplianceRecord } from "./types";
import { usePolling } from "./usePolling";
import { ErrorBox } from "./components";

const EXEC: Record<string, string> = { executed: "ejecutada", not_executed: "no ejecutada", partial: "parcial" };
const DIAG: Record<string, string> = {
  not_executed: "No ejecutada",
  within_range: "Dentro del rango",
  external_event: "Evento externo",
  forecast_error: "Error de pronóstico",
};

function Row({ r }: { r: ComplianceRecord }) {
  return (
    <li className="card" data-testid={`compliance-${r.decision_id}`}>
      <strong>{actionLabel(r.action_type ?? "—")}</strong> <span className="muted">({r.issue_id ?? r.decision_id})</span>{" "}
      {r.applicable ? (
        <span className="badge">{EXEC[r.execution_status ?? "not_executed"] ?? r.execution_status}</span>
      ) : (
        <span className="badge">{r.status}</span>
      )}
      {r.diagnosis && <span className="badge badge-warn">{DIAG[r.diagnosis] ?? r.diagnosis}</span>}
      {(r.simulated || r.observed) && (
        <p>
          {r.simulated && <span>Simulado {usd(r.simulated.net_usd_mid)}</span>}
          {r.simulated && r.observed && " · "}
          {r.observed && <span>Observado {usd(r.observed.net_usd)} ({r.observed.label})</span>}
        </p>
      )}
      {r.explanation && <p className="muted">{r.explanation}</p>}
    </li>
  );
}

/** Sentinel: did the approved decisions of this case happen, and did they pay off as simulated? */
export default function CentinelaPanel({ caseId }: { caseId: string }) {
  const api = useApi();
  const res = usePolling(() => api.getCompliance(caseId), 15_000, true, [caseId]);
  return (
    <section aria-label="Centinela">
      <h4>Centinela</h4>
      <ErrorBox error={res.error} />
      {res.data?.length === 0 && <p className="muted">Sin decisiones que verificar</p>}
      <ul style={{ listStyle: "none", padding: 0 }}>
        {res.data?.map((r) => <Row key={r.decision_id} r={r} />)}
      </ul>
    </section>
  );
}
