import { useCallback, useState } from "react";
import { useApi } from "./ApiContext";
import { ApiError } from "./api";
import type { DecisionItem, Memory } from "./data/copilot";
import { useCopilot } from "./state/copilotStore";

export interface Rejection {
  /** Label of the chosen reason chip ("" when only free text was written). */
  label: string;
  text: string;
}

/**
 * Two-step decision on the real backend: POST /proposals (reused when one is pending), then POST /proposals/{id}/decision.
 * Local state (card removed, toast, learned memory) changes only after the backend accepted the decision.
 */
export function useDecide(caseId: string, refresh: () => Promise<void> | void) {
  const api = useApi();
  const { dispatch, showToast } = useCopilot();
  const [busy, setBusy] = useState<string | null>(null);

  return useCallback(
    async (item: DecisionItem, approved: boolean, rejection?: Rejection): Promise<boolean> => {
      if (item.readOnly || !caseId) return false;
      const label = rejection?.label || "Otro";
      const reason = approved ? undefined : [rejection?.label, rejection?.text].filter(Boolean).join(": ");
      setBusy(item.id);
      try {
        const proposalId =
          item.proposalId ??
          (await api.propose({ case_id: caseId, issue_id: item.issueId, option_id: item.optionId, rationale: item.title }, { idempotencyKey: crypto.randomUUID() })).proposal_id;
        try {
          await api.decide(proposalId, approved ? { approved: true } : { approved: false, reason }, { idempotencyKey: crypto.randomUUID() });
        } catch (e) {
          if (!(e instanceof ApiError && e.status === 409)) throw e; // already decided elsewhere: reconcile below
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
        const memory: Memory = {
          id: `learned-${item.id}`,
          cat: "preferencias",
          icon: "school",
          tag: `Motivo: ${label}`,
          text: rejection?.text.trim() ? `«${rejection.text.trim()}»` : label,
          src: `Rechazo · hoy · ${item.title}`,
          conf: "Ajustará próximas propuestas",
          isNew: true,
        };
        dispatch({ type: "learned", memory });
        showToast(`Motivo registrado como «${label}». El copiloto aprenderá de esto.`);
      }
      void refresh();
      return true;
    },
    [api, caseId, dispatch, showToast, refresh],
  );
}

export type Decide = ReturnType<typeof useDecide>;
