import { useCallback, useRef, useState } from "react";
import { useApi } from "./ApiContext";
import { ApiError } from "./api";
import type { DecisionItem } from "./data/copilot";
import { useCopilot } from "./state/copilotStore";

export interface Rejection {
  /** Label of the chosen reason chip ("" when only free text was written). */
  label: string;
  text: string;
}

/** A 4xx answer settles the intent; network errors and 5xx may have reached the backend, so the same key is replayed. */
const isDefinitive = (e: unknown): boolean => e instanceof ApiError && e.status >= 400 && e.status < 500;

/**
 * Atomic decision on the real backend: POST /cases/{id}/decisions (proposal and decision in one call).
 * Local state (card removed, toast) changes only after the backend accepted the decision.
 */
export function useDecide(caseId: string, refresh: () => Promise<void> | void) {
  const api = useApi();
  const { dispatch, showToast } = useCopilot();
  const [busyId, setBusy] = useState<string | null>(null);
  // One Idempotency-Key per user intent (card x action): created when the action starts, reused on retries and double taps,
  // dropped only after a definitive outcome (success or a 4xx answer from the backend).
  const keys = useRef(new Map<string, string>());
  const inflight = useRef(new Map<string, Promise<boolean>>());

  const run = useCallback(
    async (item: DecisionItem, approved: boolean, intent: string, rejection?: Rejection): Promise<boolean> => {
      const label = rejection?.label || "Otro";
      const reason = approved ? undefined : [rejection?.label, rejection?.text].filter(Boolean).join(": ");
      const idempotencyKey = keys.current.get(intent) ?? crypto.randomUUID();
      keys.current.set(intent, idempotencyKey);
      setBusy(item.id);
      try {
        try {
          await api.recordDecision(caseId, { issue_id: item.issueId, option_id: item.optionId, approved, ...(approved ? {} : { reason }) }, { idempotencyKey });
          keys.current.delete(intent);
        } catch (e) {
          if (isDefinitive(e)) keys.current.delete(intent);
          if (!(e instanceof ApiError && e.status === 409)) throw e;
          // 409: the option was already decided elsewhere. Nothing was recorded by this click: say so, reconcile with the backend.
          showToast("Esta decisión ya se había registrado");
          void refresh();
          return true;
        }
      } catch (e) {
        showToast(`No se pudo registrar: ${(e as Error).message}`);
        return false;
      } finally {
        setBusy(null);
      }
      dispatch({ type: "handled", id: item.id, accepted: approved && item.kind === "tech" });
      if (approved) {
        showToast(`${item.kind === "approval" ? "Aprobada" : "Aceptada"}: ${item.title}. Quedó registrada.`);
      } else {
        showToast(`Motivo registrado como «${label}». El copiloto aprenderá de esto.`); // the backend creates the memory; the page refetches /memories
      }
      void refresh();
      return true;
    },
    [api, caseId, dispatch, showToast, refresh],
  );

  const decide = useCallback(
    (item: DecisionItem, approved: boolean, rejection?: Rejection): Promise<boolean> => {
      if (item.readOnly || !caseId) return Promise.resolve(false);
      // A rejection is only ever sent with a reason (the RejectSheet collects it); never fall through to anything else.
      if (!approved && !(rejection?.label || rejection?.text?.trim())) return Promise.resolve(false);
      const intent = `${item.id}:${approved ? "approve" : "reject"}`;
      const running = inflight.current.get(intent);
      if (running) return running;
      const p = run(item, approved, intent, rejection).finally(() => inflight.current.delete(intent));
      inflight.current.set(intent, p);
      return p;
    },
    [caseId, run],
  );

  return { decide, busyId };
}

export type Decide = ReturnType<typeof useDecide>["decide"];
