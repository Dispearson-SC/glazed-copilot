import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../ApiContext";
import { ErrorBox, StoreSelect, useStores } from "../components";
import CentinelaPanel from "../CentinelaPanel";
import IssueDetail from "../IssueDetail";
import { actionLabel, alertTypeLabel, kindLabel, severityCell } from "../issues";
import { useSession } from "../SessionContext";
import type { Alert, Issue, Proposal } from "../types";
import { usePolling } from "../usePolling";

const REFRESH_MS = 10_000;

function ProposalCard({ proposal, onDecided }: { proposal: Proposal; onDecided: (rejected?: Proposal) => void }) {
  const api = useApi();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<Error | null>(null);

  async function decide(approved: boolean) {
    if (!approved && !reason.trim()) {
      setError(new Error("Indica un motivo para rechazar"));
      return;
    }
    try {
      await api.decide(proposal.proposal_id, approved ? { approved } : { approved, reason: reason.trim() });
      if (approved) return onDecided();
      // The decision response is the execution; Jev's label lives on the stored proposal.
      let stored: Proposal | undefined;
      try {
        stored = (await api.listProposals({ case_id: proposal.case_id, status: "rejected" })).find(
          (p) => p.proposal_id === proposal.proposal_id,
        );
      } catch {
        /* the label is optional */
      }
      onDecided(stored ?? proposal);
    } catch (e) {
      setError(e as Error);
    }
  }

  return (
    <div className="card">
      <strong>{actionLabel(proposal.action_type)}</strong> <span className="badge">{proposal.tier}</span>
      <p>{proposal.rationale}</p>
      <pre>{JSON.stringify(proposal.params, null, 2)}</pre>
      <label>
        Motivo <input value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>{" "}
      <button onClick={() => decide(true)}>Aprobar</button> <button onClick={() => decide(false)}>Rechazar</button>
      {error && <div role="alert" className="error">{error.message}</div>}
    </div>
  );
}

function AlertDetail({ alert, onClose }: { alert: Alert; onClose: () => void }) {
  const api = useApi();
  const proposals = usePolling(() => api.listProposals({ case_id: alert.case_id, status: "pending" }), REFRESH_MS, true, [
    alert.case_id,
  ]);
  const [rejected, setRejected] = useState<Proposal | null>(null);
  return (
    <aside aria-label="Detalle de alerta" className="panel">
      <button onClick={onClose} style={{ float: "right" }}>Cerrar</button>
      <h3>Alerta {alert.alert_id}</h3>
      {Array.isArray(alert.issue.options) ? (
        <IssueDetail issue={alert.issue as Issue} caseId={alert.case_id} />
      ) : (
        <pre>{JSON.stringify(alert.issue, null, 2)}</pre>
      )}
      <h4>Propuestas pendientes</h4>
      <ErrorBox error={proposals.error} />
      {proposals.data?.length === 0 && <p className="muted">Sin propuestas pendientes</p>}
      {proposals.data?.map((p) => (
        <ProposalCard
          key={p.proposal_id}
          proposal={p}
          onDecided={(r) => {
            if (r) setRejected(r);
            void proposals.refresh();
          }}
        />
      ))}
      {rejected?.reason_category && (
        <p className="badge" role="status">
          Motivo clasificado: {rejected.reason_category}
          {typeof rejected.reason_confidence === "number" && ` (confianza ${Math.round(rejected.reason_confidence * 100)}%)`}
        </p>
      )}
      <CentinelaPanel caseId={alert.case_id} />
    </aside>
  );
}

export default function AlertsPage() {
  const api = useApi();
  const { stores, storeId, setStoreId, error: storesError } = useStores();
  const { refreshKey } = useSession();
  const [selected, setSelected] = useState<Alert | null>(null);
  const alerts = usePolling(() => (storeId ? api.listAlerts({ store_id: storeId }) : Promise.resolve([])), REFRESH_MS, true, [
    storeId,
    refreshKey,
  ]);
  const error = storesError ?? alerts.error;

  async function markSeen(a: Alert) {
    await api.setAlertState(a.alert_id, "vista");
    await alerts.refresh();
  }

  return (
    <section>
      <h2>Alertas</h2>
      <StoreSelect stores={stores} value={storeId} onChange={setStoreId} />
      <ErrorBox error={error} />
      {!error && alerts.data?.length === 0 && <p className="muted">Sin alertas</p>}
      <div className="split">
        <table>
          <thead>
            <tr><th>Tipo</th><th>Severidad / exposición (USD)</th><th>Estado</th><th>Creada</th><th>Caso</th><th /></tr>
          </thead>
          <tbody>
            {alerts.data?.map((a) => (
              <tr key={a.alert_id} data-testid={`alert-${a.alert_id}`}>
                <td>
                  <div>{alertTypeLabel(a.alert_type)}</div>
                  {typeof a.issue.kind === "string" && <div className="muted">{kindLabel(a.issue.kind)}</div>}
                </td>
                <td>{severityCell(a)}</td>
                <td><span className="badge">{a.state}</span></td>
                <td>{new Date(a.created_at).toLocaleString()}</td>
                <td><Link to={`/stores/${a.store_id}/trace?case=${a.case_id}`}>{a.case_id}</Link></td>
                <td>
                  {a.state === "nueva" && <button onClick={() => void markSeen(a)}>Marcar vista</button>}{" "}
                  <button onClick={() => setSelected(a)}>Ver detalle</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {selected && <AlertDetail alert={selected} onClose={() => setSelected(null)} />}
      </div>
    </section>
  );
}
