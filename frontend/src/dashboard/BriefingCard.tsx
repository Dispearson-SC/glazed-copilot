import { Link } from "react-router-dom";
import { ErrorBox } from "../components";
import type { Briefing } from "../types";

export default function BriefingCard({ briefing, error }: { briefing: Briefing | null; error: Error | null }) {
  const plan = briefing?.snapshot?.order_plan;
  const focus = briefing?.suggested_focus ?? [];
  return (
    <section data-testid="briefing" className="bg-surface-container-lowest rounded-[18px] p-space-lg shadow-sm shadow-primary/5 flex flex-col gap-space-sm">
      <h2 className="font-headline-sm text-headline-sm text-primary">Resumen del copiloto</h2>
      <ErrorBox error={error} />
      <ul className="flex flex-col gap-1.5 text-body-md text-on-surface list-none p-0 m-0">
        {(briefing?.headline ?? []).map((h) => (
          <li key={h.key} className="flex gap-2">
            <span aria-hidden="true" className="material-symbols-outlined text-[18px] text-secondary">arrow_right</span>
            <span>{h.text}</span>
          </li>
        ))}
      </ul>
      {plan && (
        <div className="flex gap-space-sm text-label-md">
          <span className="px-2.5 py-1 rounded-full bg-surface-container text-secondary">
            Pedidos hoy: <strong data-testid="due-today">{plan.due_today?.length ?? 0}</strong>
          </span>
          <span className="px-2.5 py-1 rounded-full bg-surface-container text-secondary">
            Mañana: <strong data-testid="due-tomorrow">{plan.due_tomorrow?.length ?? 0}</strong>
          </span>
        </div>
      )}
      {focus.length > 0 && (
        <p data-testid="focus" className="text-body-md">
          Enfoque sugerido: <strong>{focus.length}</strong> {focus.length === 1 ? "asunto" : "asuntos"} ·{" "}
          <Link className="text-secondary underline underline-offset-2" to="/alerts">Revisar alertas</Link>
        </p>
      )}
    </section>
  );
}
