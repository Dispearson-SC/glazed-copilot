import type { ForecastAccuracy as Accuracy } from "../types";

const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
const LABELS: Record<string, string> = { "1": "1 día", "2-3": "2–3 días", "4-14": "4–14 días", non_perishable: "No perecedero" };
const ORDER = ["1", "2-3", "4-14", "non_perishable"];

export default function ForecastAccuracy({ accuracy }: { accuracy: Accuracy }) {
  const keys = [...Object.keys(accuracy.groups)].sort((a, b) => {
    const ia = ORDER.indexOf(a), ib = ORDER.indexOf(b);
    return ia === -1 && ib === -1 ? a.localeCompare(b) : (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
  const rows = [...keys.map((k) => [k, LABELS[k] ?? k, accuracy.groups[k]] as const), ["__total", "Total", accuracy.overall] as const];
  return (
    <div data-testid="accuracy" className="flex flex-col gap-space-xs">
      <h3 className="font-label-md text-label-md text-secondary">Precisión del pronóstico por vida útil</h3>
      <table className="w-full text-label-md text-left">
        <thead>
          <tr className="text-on-surface-variant">
            <th scope="col">Grupo</th><th scope="col">Error (WAPE)</th><th scope="col">Sesgo</th><th scope="col">Cobertura</th><th scope="col">Días</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([key, label, m]) => (
            <tr key={key} data-testid={`accuracy-row-${key === "__total" ? "total" : key}`}>
              <th scope="row" className="font-normal">{label}</th>
              <td>{pct(m.wape)}</td>
              <td>{pct(m.bias)}</td>
              <td>{pct(m.coverage_p10_p90)}</td>
              <td>{m.n_days}{m.n_censored ? ` (${m.n_censored} con quiebre)` : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="font-label-sm text-label-sm text-on-surface-variant">
        Modelo {accuracy.model} · {accuracy.window.from} a {accuracy.window.to} · unidades. Los días con quiebre no cuentan como error.
      </p>
    </div>
  );
}
