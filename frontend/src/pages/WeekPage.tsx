import { useParams } from "react-router-dom";
import { useApi } from "../ApiContext";
import ComingSoon from "../ComingSoon";
import { longDate } from "../dashboard/format";
import { ErrorBox } from "../components";
import { usd } from "../issues";
import { useSession } from "../SessionContext";
import { useCurrentCase } from "../useCurrentCase";
import { useOptionalPolling } from "../useOptionalPolling";

const card = "bg-surface-container-lowest rounded-[18px] p-space-lg shadow-sm shadow-primary/5 flex flex-col gap-space-sm";
const DELIVERY_STATUS = { on_time: "a tiempo", late: "tarde", expected: "esperada" } as const;
const PROMO_STATUS = { active: "Activa", upcoming: "Próxima", past: "Terminada" } as const;
const h = (n: number) => `${n.toFixed(1)} h`;

export default function WeekPage() {
  const api = useApi();
  const { storeId = "" } = useParams();
  const session = useSession();
  const { currentCase, loading, error: caseError } = useCurrentCase(storeId, session.refreshKey);
  const caseId = currentCase?.case_id;
  const simToday = currentCase?.sim_today ?? "";
  const deps = [caseId, session.refreshKey];
  const deliveries = useOptionalPolling(() => (caseId ? api.getDeliveries(caseId, { days: "7" }) : Promise.resolve(null)), 60_000, false, deps);
  const promos = useOptionalPolling(() => (caseId ? api.getPromos(caseId, { days: "14" }) : Promise.resolve(null)), 60_000, false, deps);
  const staffing = useOptionalPolling(() => (caseId ? api.getStaffing(caseId, { days: "7" }) : Promise.resolve(null)), 60_000, false, deps);
  const error = caseError ?? deliveries.error ?? promos.error ?? staffing.error;
  return (
    <section className="flex flex-col gap-space-md">
      <h2 className="font-headline-sm text-headline-sm text-primary">Semana</h2>
      <ErrorBox error={error} />
      {!error && !loading && !currentCase && <p className="muted">Sin caso activo para esta sucursal</p>}
      {currentCase && (
        <>
          <div className={card}>
            <h3 className="font-label-md text-label-md text-secondary">Entregas esperadas</h3>
            {deliveries.soon && <ComingSoon what="Entregas" />}
            {deliveries.data?.days.map((d) => (
              <div key={d.date} data-testid={`delivery-${d.date}`} className="text-body-md">
                <div className="font-bold capitalize">{longDate(d.date)}</div>
                {d.deliveries.length === 0 && <div className="text-on-surface-variant">Sin entregas</div>}
                {d.deliveries.map((x, i) => (
                  <div key={`${x.supplier_id}-${i}`} className="text-label-md text-on-surface-variant">
                    {x.supplier_name}
                    {x.po_id ? ` · ${x.po_id}` : " · programada"} · {x.lines.map((l) => `${l.product_name} (${l.qty})`).join(", ")} · {usd(x.value_usd)} · {DELIVERY_STATUS[x.status]}
                  </div>
                ))}
              </div>
            ))}
          </div>
          <div className={card}>
            <h3 className="font-label-md text-label-md text-secondary">Promociones</h3>
            {promos.soon && <ComingSoon what="Promociones" />}
            {promos.data && promos.data.items.length === 0 && <p className="text-body-md text-on-surface-variant">Sin promociones en este periodo</p>}
            {promos.data?.items.map((p) => {
              // An uplift only exists once the promo has ended; never show it earlier.
              const finished = simToday !== "" && p.end_date <= simToday;
              return (
                <div key={p.promo_id} data-testid={`promo-${p.promo_id}`} className="text-body-md">
                  <span className="font-bold">{p.name}</span> · {p.department} · {p.discount_pct}% · {p.start_date} a {p.end_date} · {PROMO_STATUS[p.status]}
                  {p.audit_verdict && <div className="text-label-md text-on-surface-variant">Auditoría: {p.audit_verdict}</div>}
                  {finished && p.evaluation && (
                    <div className="text-label-md text-on-surface-variant">Efecto en ventas: {p.evaluation.uplift_pct >= 0 ? "+" : ""}{p.evaluation.uplift_pct}%</div>
                  )}
                </div>
              );
            })}
          </div>
          <div data-testid="staffing" className={card}>
            <h3 className="font-label-md text-label-md text-secondary">Personal (proyección)</h3>
            <p className="text-label-md text-on-surface-variant">Solo por día: no hay desglose por hora.</p>
            {staffing.soon && <ComingSoon what="Personal" />}
            {staffing.data && (
              <>
                <p className="text-label-md text-on-surface-variant">{staffing.data.note}</p>
                <ul className="flex flex-col gap-1 list-none p-0 m-0">
                  {staffing.data.days.map((d) => (
                    <li key={d.date} data-testid={`staffing-${d.date}`} className="text-body-md">
                      {longDate(d.date)} · {Math.round(d.forecast_transactions)} transacciones · recomendado <span>{h(d.recommended_staff_hours)}</span>
                      {" · planeado "}
                      {d.planned_staff_hours == null ? "Sin datos" : h(d.planned_staff_hours)}
                      {d.gap_hours != null && ` · diferencia ${d.gap_hours >= 0 ? "+" : ""}${h(d.gap_hours)}`}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </>
      )}
    </section>
  );
}
