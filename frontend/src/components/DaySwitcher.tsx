import { useEffect, useRef, useState } from "react";
import { useApi } from "../ApiContext";
import { MAX_SIM_DATE, MIN_SIM_DATE } from "../config";
import { shiftDate } from "../format";
import { useSession } from "../SessionContext";
import { ensureCaseAt, liveAt, useCurrentCase } from "../useCurrentCase";
import { usePolling } from "../usePolling";
import Toast from "./copilot/Toast";

const dayLabel = (iso: string) =>
  new Intl.DateTimeFormat("es-MX", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(`${iso.slice(0, 10)}T00:00:00Z`))
    .replace(/\./g, "");

const outcomesText = (n: number) => (n === 1 ? "1 resultado de decisión disponible" : `${n} resultados de decisiones disponibles`);

const btn =
  "-my-2 flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full border-0 bg-transparent p-0 text-secondary disabled:opacity-35";

/** Discreet demo control: ◀ date ▶. Forward advances the case clock; back switches to the previous day's case. */
export default function DaySwitcher({ storeId, className = "" }: { storeId: string; className?: string }) {
  const api = useApi();
  const session = useSession();
  const { currentCase } = useCurrentCase(storeId, session.refreshKey);
  const cases = usePolling(
    () => (storeId ? api.listCases({ store_id: storeId }) : Promise.resolve([])),
    60_000,
    false,
    [storeId, session.refreshKey, currentCase?.case_id],
  );
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  const date = currentCase?.sim_today ?? "";
  const latest = (cases.data ?? []).reduce((m, c) => (c.mode === "live" && c.sim_today > m ? c.sim_today : m), "");
  const behind = Boolean(date && latest > date);

  const say = (text: string) => {
    setToast(text);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(null), 3200);
  };

  const forward = async () => {
    if (!currentCase || busy) return;
    setBusy(true);
    try {
      const next = shiftDate(currentCase.sim_today, 1);
      let list = await api.listCases({ store_id: storeId });
      const existing = liveAt(list, next)[0];
      if (existing) {
        session.setCaseId(existing.case_id, storeId);
        session.bump();
        return;
      }
      const newest = list.reduce((m, c) => (c.mode === "live" && c.sim_today > m ? c.sim_today : m), "");
      if (currentCase.sim_today >= newest) {
        const res = await api.advanceCase(currentCase.case_id, { days: 1 });
        const n = res.outcomes?.length ?? 0;
        if (n > 0) say(outcomesText(n));
        session.bump();
        return;
      }
      // An older case never moves its clock: open (or create, once) the case of the next date instead.
      list = await ensureCaseAt(api, storeId, next);
      const pick = liveAt(list, next)[0];
      if (pick) {
        session.setCaseId(pick.case_id, storeId);
        session.bump();
      }
    } catch (e) {
      say((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const back = async () => {
    if (!currentCase || busy) return;
    setBusy(true);
    try {
      const target = shiftDate(currentCase.sim_today, -1);
      let list = await api.listCases({ store_id: storeId });
      if (liveAt(list, target).length === 0) list = await ensureCaseAt(api, storeId, target);
      const pick = liveAt(list, target)[0];
      if (pick) {
        session.setCaseId(pick.case_id, storeId);
        session.bump();
      }
    } catch (e) {
      say((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!currentCase) return null;
  return (
    <div className={`flex flex-col items-center ${className}`}>
      <div role="group" aria-label="Cambiar día" className="flex h-7 items-center rounded-full border border-partition/60 bg-elevation px-1">
        <button type="button" aria-label="Día anterior" disabled={busy || date <= MIN_SIM_DATE} onClick={() => void back()} className={btn}>
          <span aria-hidden="true" className="material-symbols-outlined text-[18px]">chevron_left</span>
        </button>
        <span data-testid="day-switcher-date" className="min-w-[96px] px-1 text-center font-label-sm text-label-sm text-on-surface-variant">
          {dayLabel(date)}
        </span>
        <button type="button" aria-label="Día siguiente" disabled={busy || date >= MAX_SIM_DATE} onClick={() => void forward()} className={btn}>
          <span aria-hidden="true" className="material-symbols-outlined text-[18px]">chevron_right</span>
        </button>
      </div>
      {behind && <p className="mt-0.5 text-center font-label-sm text-label-sm text-on-surface-variant">Las decisiones de fechas posteriores no aparecen aquí</p>}
      <Toast text={toast} />
    </div>
  );
}
