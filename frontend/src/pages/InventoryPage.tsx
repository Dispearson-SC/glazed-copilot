import { useState } from "react";
import { useParams } from "react-router-dom";
import { useApi } from "../ApiContext";
import ComingSoon from "../ComingSoon";
import { ErrorBox } from "../components";
import { asRange, rangeOrValue, usd } from "../issues";
import { useSession } from "../SessionContext";
import type { InventorySort } from "../types";
import { useCurrentCase } from "../useCurrentCase";
import { useOptionalPolling } from "../useOptionalPolling";

const card = "bg-surface-container-lowest rounded-[18px] p-space-lg shadow-sm shadow-primary/5 flex flex-col gap-space-sm";
const SORTS: { key: InventorySort; label: string }[] = [
  { key: "days_of_cover", label: "Cobertura" },
  { key: "turnover", label: "Rotación" },
  { key: "slow", label: "Lentos" },
];
const num = (n: number | null | undefined, d = 1) => (n == null ? "—" : n.toFixed(d));

export default function InventoryPage() {
  const api = useApi();
  const { storeId = "" } = useParams();
  const session = useSession();
  const { currentCase, loading, error: caseError } = useCurrentCase(storeId, session.refreshKey);
  const caseId = currentCase?.case_id;
  const [sort, setSort] = useState<InventorySort>("days_of_cover");
  const inv = useOptionalPolling(
    () => (caseId ? api.getInventory(caseId, { sort, limit: "50" }) : Promise.resolve(null)),
    60_000,
    false,
    [caseId, sort, session.refreshKey],
  );
  const exp = useOptionalPolling(
    () => (caseId ? api.getExpiring(caseId, { days: "7" }) : Promise.resolve(null)),
    60_000,
    false,
    [caseId, session.refreshKey],
  );
  const error = caseError ?? inv.error ?? exp.error;
  return (
    <section className="flex flex-col gap-space-md">
      <h2 className="font-headline-sm text-headline-sm text-primary">Inventario</h2>
      <ErrorBox error={error} />
      {!error && !loading && !currentCase && <p className="muted">Sin caso activo para esta sucursal</p>}
      {currentCase && (
        <div className={card}>
          <div className="flex gap-space-xs" role="group" aria-label="Ordenar por">
            {SORTS.map((s) => (
              <button key={s.key} type="button" aria-pressed={sort === s.key} onClick={() => setSort(s.key)}
                className={`px-3 py-1 rounded-full text-label-md ${sort === s.key ? "bg-secondary text-surface-container-lowest" : "bg-surface-container"}`}>
                {s.label}
              </button>
            ))}
          </div>
          {inv.soon && <ComingSoon what="Inventario" />}
          {inv.data && (
            <>
              <p data-testid="inventory-coverage" className="text-body-md">
                Inventario disponible para {inv.data.coverage.skus_with_inventory} de {inv.data.coverage.skus_selling} productos
              </p>
              <table className="w-full text-label-md text-left">
                <thead>
                  <tr className="text-on-surface-variant">
                    <th scope="col">Producto</th><th scope="col">Existencia</th><th scope="col">Días de cobertura</th>
                    <th scope="col">Rotación 28 d</th><th scope="col">Valor</th><th scope="col">Última venta</th><th scope="col">Se agota (proyección)</th>
                  </tr>
                </thead>
                <tbody>
                  {inv.data.items.map((i) => (
                    <tr key={i.sku} data-testid={`inv-${i.sku}`}>
                      <th scope="row" className="font-normal">
                        {i.product_name}
                        {i.slow_mover && <span className="ml-1 px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant">lento</span>}
                      </th>
                      <td>{i.on_hand}</td>
                      <td>{num(i.days_of_cover)}</td>
                      <td>{num(i.turnover_28d)}</td>
                      <td>{usd(i.inventory_value_usd)}</td>
                      <td>{i.last_sale_date ?? "—"}</td>
                      <td>{i.projected_stockout_date ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
      {currentCase && (
        <div className={card}>
          <h3 className="font-label-md text-label-md text-secondary">Por caducar (próximos 7 días, proyección)</h3>
          {exp.soon && <ComingSoon what="Caducidades" />}
          {exp.data && (
            <div data-testid="expiring" className="flex flex-col gap-space-xs">
              {exp.data.items.length === 0 && <p className="text-body-md text-on-surface-variant">Nada por caducar esta semana</p>}
              <ul className="flex flex-col gap-space-sm list-none p-0 m-0">
                {exp.data.items.map((i) => (
                  <li key={`${i.sku}-${i.expiry_date}`} className="text-body-md">
                    <span className="font-bold">{i.product_name}</span> · {i.expiring_units} pzas · caduca {i.expiry_date}
                    <div className="text-label-md text-on-surface-variant">
                      Merma esperada {rangeOrValue(asRange(i.waste_usd))}
                      {i.lot_age_inferred && " · edad del lote estimada"}
                    </div>
                  </li>
                ))}
              </ul>
              <p data-testid="expiring-total" className="text-body-md">
                Merma total esperada: <strong>{rangeOrValue(asRange(exp.data.total_waste_usd))}</strong>
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
