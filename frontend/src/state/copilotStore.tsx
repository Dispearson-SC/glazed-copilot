import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, type ReactNode } from "react";
import type { AnalysisRef, CopilotContext, DayKey, Tab } from "../data/copilot";

export interface CopilotState {
  tab: Tab;
  day: DayKey;
  memFilter: string;
  alertFilter: string;
  ctx: CopilotContext | null;
  /** Card whose ⋯ menu is open. */
  menuFor: string | null;
  /** Card whose reject sheet is open. */
  rejectFor: string | null;
  toast: string | null;
  /** Tech decisions accepted by the manager in this session. */
  accepted: number;
  /** Ids already decided (accepted, approved or rejected) in this session. */
  handled: string[];
  analyses: AnalysisRef[];
  seq: number;
}

export const initialCopilotState: CopilotState = {
  tab: "agente",
  day: "hoy",
  memFilter: "todas",
  alertFilter: "todas",
  ctx: null,
  menuFor: null,
  rejectFor: null,
  toast: null,
  accepted: 0,
  handled: [],
  analyses: [],
  seq: 1,
};

export type CopilotAction =
  | { type: "tab"; tab: Tab }
  | { type: "day"; day: DayKey }
  | { type: "memFilter"; value: string }
  | { type: "alertFilter"; value: string }
  | { type: "ctx"; ctx: CopilotContext | null }
  | { type: "toggleMenu"; id: string }
  | { type: "openReject"; id: string }
  | { type: "closeReject" }
  | { type: "toast"; text: string | null }
  | { type: "analysis"; itemId: string; title: string; mode: AnalysisRef["mode"]; at: number; issueId?: string; optionId?: string }
  | { type: "handled"; id: string; accepted: boolean };

export function copilotReducer(s: CopilotState, a: CopilotAction): CopilotState {
  switch (a.type) {
    case "tab":
      return { ...s, tab: a.tab, menuFor: null };
    case "day":
      return { ...s, day: a.day };
    case "memFilter":
      return { ...s, memFilter: a.value };
    case "alertFilter":
      return { ...s, alertFilter: a.value };
    case "ctx":
      return { ...s, ctx: a.ctx };
    case "toggleMenu":
      return { ...s, menuFor: s.menuFor === a.id ? null : a.id };
    case "openReject":
      return { ...s, rejectFor: a.id, menuFor: null };
    case "closeReject":
      return { ...s, rejectFor: null };
    case "toast":
      return { ...s, toast: a.text };
    case "analysis":
      return {
        ...s,
        tab: "agente",
        menuFor: null,
        ctx: { id: a.itemId, title: a.title, ...(a.issueId ? { issueId: a.issueId } : {}), ...(a.optionId ? { optionId: a.optionId } : {}) },
        analyses: [...s.analyses, { id: `an-${s.seq}`, itemId: a.itemId, mode: a.mode, at: a.at }],
        seq: s.seq + 1,
      };
    case "handled":
      if (s.handled.includes(a.id)) return s;
      return { ...s, handled: [...s.handled, a.id], accepted: s.accepted + (a.accepted ? 1 : 0), menuFor: null };
  }
}

const TOAST_MS = 3200;

interface CopilotCtxValue {
  state: CopilotState;
  dispatch: (a: CopilotAction) => void;
  showToast: (text: string) => void;
}

const Ctx = createContext<CopilotCtxValue | null>(null);

export function CopilotProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(copilotReducer, initialCopilotState);
  const showToast = useCallback((text: string) => dispatch({ type: "toast", text }), []);

  // Every new toast restarts the 3.2 s timer.
  useEffect(() => {
    if (!state.toast) return;
    const id = setTimeout(() => dispatch({ type: "toast", text: null }), TOAST_MS);
    return () => clearTimeout(id);
  }, [state.toast]);

  const value = useMemo(() => ({ state, dispatch, showToast }), [state, showToast]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCopilot(): CopilotCtxValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useCopilot must be used inside <CopilotProvider>");
  return v;
}
