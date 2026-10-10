import { useState } from "react";
import { useApi } from "./ApiContext";
import { bestOption, isLowConfidence, rangeText, tierInfo, usd } from "./issues";
import type { Issue, Option } from "./types";

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  return (
    <div>
      <div role="progressbar" aria-label="Confianza" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} className="bar">
        <div className="bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="muted">Confianza {pct}%</span>
      {isLowConfidence(score) && <span className="badge badge-warn"> baja confianza</span>}
    </div>
  );
}

function OptionCard({ issue, option, caseId, best }: { issue: Issue; option: Option; caseId: string; best: boolean }) {
  const api = useApi();
  const [proposalId, setProposalId] = useState<string | null>(null);
  const [approved, setApproved] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const tier = tierInfo(option.tier);
  const nothing = option.action_type === "do_nothing";

  async function propose() {
    try {
      const p = await api.proposeOption({
        case_id: caseId,
        issue_id: issue.issue_id,
        option_id: option.option_id,
        rationale: `Opción ${option.action_type} (neto estimado ${usd(option.net_usd_mid)})`,
      });
      setProposalId(p.proposal_id);
      setError(null);
    } catch (e) {
      setError(e as Error);
    }
  }
  async function approve() {
    if (!proposalId) return;
    try {
      await api.decide(proposalId, { approved: true });
      setApproved(true);
      setError(null);
    } catch (e) {
      setError(e as Error);
    }
  }

  return (
    <div className={`card option${best ? " best" : ""}`} data-testid={`option-${option.option_id}`}>
      <strong>{nothing ? "No hacer nada" : option.action_type}</strong>{" "}
      <span className={`badge ${tier.className}`}>{tier.label}</span>
      {best && <span className="badge badge-best"> más viable</span>}
      <p>
        {nothing ? "Costo de no actuar" : "Neto estimado"}:{" "}
        <strong>{nothing ? usd(Math.abs(option.net_usd_mid)) : usd(option.net_usd_mid)}</strong>
      </p>
      {!nothing && <p className="muted">Beneficio <span>{rangeText(option.expected_benefit_usd)}</span> · costo {usd(option.cost_usd)}</p>}
      <p>
        merma Δ {usd(option.loss_impact.waste_usd_delta)} · ventas perdidas Δ {usd(option.loss_impact.lost_sales_usd_delta)}
      </p>
      <ConfidenceBar score={option.confidence.score} />
      {option.tier_reasons.length > 0 && <p className="muted">Nivel: {option.tier_reasons.join("; ")}</p>}
      {(option.urgency.deadline_date || option.urgency.reason) && (
        <p>
          Urgencia: {option.urgency.deadline_date ?? ""} {option.urgency.reason}
        </p>
      )}
      {option.risk.length > 0 && (
        <ul>
          {option.risk.map((r) => (
            <li key={r}>Riesgo: {r}</li>
          ))}
        </ul>
      )}
      {option.if_act && <p>Si actúas: {option.if_act}</p>}
      {option.if_not && <p>Si no actúas: {option.if_not}</p>}
      {!nothing && option.tier !== "N0" && !proposalId && <button onClick={() => void propose()}>Proponer esta opción</button>}
      {proposalId && !approved && <button onClick={() => void approve()}>Aprobar</button>}
      {approved && <span className="badge">Aprobada</span>}
      {error && <div role="alert" className="error">{error.message}</div>}
    </div>
  );
}

export default function IssueDetail({ issue, caseId }: { issue: Issue; caseId: string }) {
  const best = bestOption(issue.options);
  return (
    <div>
      <h4>Evidencia</h4>
      {issue.evidence.length === 0 ? (
        <p className="muted">Sin evidencia</p>
      ) : (
        <ul>
          {issue.evidence.map((e, i) => (
            <li key={i}>
              {e.metric}: {e.value} {e.unit} ({e.period}) <span className="muted">fuente {e.source}</span>
            </li>
          ))}
        </ul>
      )}
      {issue.data_caveats.length > 0 && (
        <div className="caveats">
          <h4>Limitaciones de los datos</h4>
          <ul>
            {issue.data_caveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      )}
      <h4>Opciones</h4>
      {issue.options.map((o) => (
        <OptionCard key={o.option_id} issue={issue} option={o} caseId={caseId} best={best?.option_id === o.option_id} />
      ))}
    </div>
  );
}
