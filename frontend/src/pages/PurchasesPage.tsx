import { useState } from "react";
import { useParams } from "react-router-dom";
import { useApi } from "../ApiContext";
import { ErrorBox } from "../components";
import IssueDetail from "../IssueDetail";
import { asRange, deadlineUrgency, usd } from "../issues";
import { useSession } from "../SessionContext";
import type { Issue, OrderLine } from "../types";
import { useCurrentCase } from "../useCurrentCase";
import { usePolling } from "../usePolling";

const URGENCY_TEXT = { today: "hoy", tomorrow: "mañana", overdue: "vencido" } as const;
const pct = (n: number) => `${Math.round(n * 100)}%`;

function MiniBar({ waste, lost }: { waste: number; lost: number }) {
  const total = waste + lost || 1;
  return (
    <div data-testid="minibar">
      <div className="minibar">
        <span className="seg-waste" style={{ width: `${(waste / total) * 100}%` }} />
        <span className="seg-lost" style={{ width: `${(lost / total) * 100}%` }} />
      </div>
      <span className="muted">merma {usd(waste)} · ventas perdidas {usd(lost)}</span>
    </div>
  );
}

function Line({ line, simToday, onOpen }: { line: OrderLine; simToday: string; onOpen: (i: Issue) => void }) {
  const urgency = deadlineUrgency(line.order_deadline, simToday);
  const qtyRange = line.qty_low !== undefined && line.qty_high !== undefined ? ` (${line.qty_low}–${line.qty_high})` : "";
  const vs = line.vs_current_practice;
  return (
    <tr data-testid={`line-${line.sku}`}>
      <td>{line.name ?? line.sku}</td>
      <td>
        {line.qty} pzas{qtyRange}
        {line.cases !== undefined && line.case_size !== undefined && (
          <div className="muted">{line.cases} cajas de {line.case_size}</div>
        )}
      </td>
      <td>
        <span data-testid="deadline" className={urgency ? `deadline-${urgency}` : ""}>
          {line.order_deadline ?? "—"}
          {urgency && ` (${URGENCY_TEXT[urgency]})`}
        </span>
      </td>
      <td>
        Quiebre: {line.projected_stockout_date ?? "—"}
        <div>Riesgo sin pedir: {pct(line.stockout_risk_without_order)}</div>
      </td>
      <td>Nivel de servicio {pct(line.service_level_target)}</td>
      <td>
        hoy recibes {vs.received_to_sold.toFixed(1)}× lo que vendes
        {line.min_order_warning && (
          <div>
            <span className="badge badge-soft" data-testid="min-warning">
              {typeof line.min_order_warning === "string"
                ? line.min_order_warning
                : `Pedido ${usd(line.min_order_warning.order_value_usd)} bajo el mínimo de ${usd(line.min_order_warning.min_order_value)}`}
            </span>
          </div>
        )}
      </td>
      <td>
        {line.expected_waste_usd !== undefined && line.expected_lost_sales_usd !== undefined && (
          <MiniBar waste={asRange(line.expected_waste_usd).mid} lost={asRange(line.expected_lost_sales_usd).mid} />
        )}
      </td>
      <td>{line.issue && <button onClick={() => onOpen(line.issue!)}>Ver opciones</button>}</td>
    </tr>
  );
}

export default function PurchasesPage() {
  const api = useApi();
  const { storeId = "" } = useParams();
  const session = useSession();
  const { currentCase, loading, error: caseError } = useCurrentCase(storeId, session.refreshKey);
  const caseId = currentCase?.case_id;
  const plan = usePolling(() => (caseId ? api.getOrderPlan(caseId) : Promise.resolve(null)), 30_000, true, [
    caseId,
    session.refreshKey,
  ]);
  const [issue, setIssue] = useState<Issue | null>(null);
  const error = caseError ?? plan.error;
  const lines = plan.data?.lines ?? [];
  const suppliers = [...new Set(lines.map((l) => l.supplier_id))];

  return (
    <section>
      <h2>Compras</h2>
      <ErrorBox error={error} />
      {!error && !loading && !currentCase && <p className="muted">Sin caso activo para esta sucursal</p>}
      {!error && plan.data && lines.length === 0 && <p className="muted">Sin pedidos sugeridos</p>}
      <div className="split">
        <div>
          {suppliers.map((sid) => {
            const group = lines.filter((l) => l.supplier_id === sid);
            return (
              <div key={sid} className="card" data-testid={`supplier-${sid}`}>
                <h3>{group[0].supplier_name ?? sid}</h3>
                <table>
                  <tbody>
                    {group.map((l) => (
                      <Line key={l.sku} line={l} simToday={currentCase?.sim_today ?? plan.data?.as_of ?? ""} onOpen={setIssue} />
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })}
        </div>
        {issue && caseId && (
          <aside aria-label="Detalle del problema" className="panel">
            <button onClick={() => setIssue(null)} style={{ float: "right" }}>Cerrar</button>
            <h3>{issue.kind} {issue.sku ?? ""}</h3>
            <IssueDetail issue={issue} caseId={caseId} />
          </aside>
        )}
      </div>
    </section>
  );
}
