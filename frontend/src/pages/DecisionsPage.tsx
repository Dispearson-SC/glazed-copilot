import { useParams } from "react-router-dom";
import { useApi } from "../ApiContext";
import ComingSoon from "../ComingSoon";
import { ErrorBox } from "../components";
import { actionLabel, rangeOrValue, usd } from "../issues";
import { useSession } from "../SessionContext";
import type { DecisionRow } from "../types";
import { useCurrentCase } from "../useCurrentCase";
import { useOptionalPolling } from "../useOptionalPolling";

const card = "bg-surface-container-lowest rounded-[18px] p-space-lg shadow-sm shadow-primary/5 flex flex-col gap-space-sm";

const STATUS_WORD: Record<string, string> = { approved: "Aprobada", rejected: "Rechazada" };

function stepLabel(r: DecisionRow): string {
  switch (r.kind) {
    case "proposal": return "Propuesta";
    case "skip_order": return "Pedido omitido";
    case "decision": return STATUS_WORD[r.status] ?? "Decisión";
    case "execution": return r.status === "executed" ? "Ejecución: ejecutada" : `Ejecución: ${r.status}`;
    case "outcome": return "Resultado";
  }
}

function Outcome({ row }: { row: DecisionRow }) {
  const o = row.outcome;
  if (!o) return null;
  const sim = o.simulated;
  const range = { low: sim.net_usd_low ?? sim.net_usd_mid, mid: sim.net_usd_mid, high: sim.net_usd_high ?? sim.net_usd_mid };
  const net = o.observed.net_usd;
  return (
    <div data-testid={`outcome-${row.decision_id}`} className="text-label-md text-on-surface-variant">
      Esperado {usd(sim.net_usd_mid)} ({rangeOrValue(range)}) · Observado {net === undefined ? "sin datos" : usd(net)} · {o.label}
      {o.score?.within_expected_range !== undefined && ` · ${o.score.within_expected_range ? "dentro del rango" : "fuera del rango"}`}
    </div>
  );
}

function Group({ rows }: { rows: DecisionRow[] }) {
  const first = rows[0];
  return (
    <article data-testid={`decision-${first.decision_id}`} className={card}>
      <h3 className="font-label-md text-label-md text-primary">
        {actionLabel(first.action_type)}
        {first.sku ? ` · ${first.sku}` : ""}
        {first.supplier ? ` · ${first.supplier}` : ""}
        {first.qty !== undefined ? ` · ${first.qty} pzas` : ""}
      </h3>
      <ol className="flex flex-col gap-1.5 list-none p-0 m-0">
        {rows.map((r, i) => (
          <li key={`${r.kind}-${i}`} className="text-body-md">
            <span className="font-bold">{stepLabel(r)}</span>
            <span className="text-on-surface-variant text-label-md"> · {r.ts.slice(0, 16).replace("T", " ")}</span>
            {r.reason && <span className="text-on-surface-variant"> · {r.reason}</span>}
            {r.kind === "outcome" && <Outcome row={r} />}
          </li>
        ))}
      </ol>
    </article>
  );
}

export default function DecisionsPage() {
  const api = useApi();
  const { storeId = "" } = useParams();
  const session = useSession();
  const { currentCase, loading, error: caseError } = useCurrentCase(storeId, session.refreshKey);
  const caseId = currentCase?.case_id;
  const simToday = currentCase?.sim_today;
  const res = useOptionalPolling(() => (caseId ? api.getDecisions(caseId) : Promise.resolve(null)), 30_000, true, [caseId, session.refreshKey]);
  // Look-ahead guard: a measured outcome whose horizon ends after sim_today does not exist yet.
  const rows = (res.data ?? []).filter((r) => !(r.kind === "outcome" && simToday && r.as_of && r.as_of > simToday));
  const groups: DecisionRow[][] = [];
  for (const r of rows) {
    const g = groups.find((x) => x[0].decision_id === r.decision_id);
    if (g) g.push(r);
    else groups.push([r]);
  }
  const error = caseError ?? res.error;
  return (
    <section className="flex flex-col gap-space-md">
      <h2 className="font-headline-sm text-headline-sm text-primary">Decisiones</h2>
      <ErrorBox error={error} />
      {!error && !loading && !currentCase && <p className="muted">Sin caso activo para esta sucursal</p>}
      {res.soon && <ComingSoon what="Historial de decisiones" />}
      {res.data && groups.length === 0 && <p className="muted">Aún no hay decisiones en este caso</p>}
      {groups.map((g) => <Group key={g[0].decision_id} rows={g} />)}
    </section>
  );
}
