import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "./ApiContext";
import { useSession } from "./SessionContext";
import type { Case } from "./types";
import { usePolling } from "./usePolling";

const two = (n: number) => String(n).padStart(2, "0");

/** Conversations of a store and sim date: plain cases (not archived, not tied to an issue), newest first. */
export const conversationsOf = (cases: Case[], storeId: string, simToday: string): Case[] =>
  cases
    .filter((c) => c.store_id === storeId && c.sim_today === simToday && c.archived !== true && c.issue_key == null)
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));

/** Earlier conversations plus "new conversation"; previews (the first user message) load lazily once `open`. */
export function useConversations(storeId: string, simToday: string, caseId: string, open: boolean) {
  const api = useApi();
  const session = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const asked = useRef(new Set<string>());
  const list = usePolling(
    () => (storeId ? api.listCases({ store_id: storeId }) : Promise.resolve([])),
    60_000,
    false,
    [storeId, session.refreshKey, caseId],
  );
  const conversations = conversationsOf(list.data ?? [], storeId, simToday);

  const ids = conversations.map((c) => c.case_id).join(",");
  useEffect(() => {
    if (!open) return;
    for (const id of ids ? ids.split(",") : []) {
      if (asked.current.has(id)) continue;
      asked.current.add(id);
      api
        .listTurns(id)
        .then((turns) => setPreviews((p) => ({ ...p, [id]: turns.find((t) => t.user_text?.trim())?.user_text.trim() ?? "" })))
        .catch(() => setPreviews((p) => ({ ...p, [id]: "" })));
    }
  }, [api, open, ids]);

  const startNew = useCallback(async () => {
    if (!storeId || !simToday || busy) return;
    setBusy(true);
    setError(null);
    try {
      const now = new Date();
      const created = await api.createCase({ store_id: storeId, sim_today: simToday, mode: "live", title: `Conversación ${two(now.getHours())}:${two(now.getMinutes())}` });
      session.setCaseId(created.case_id, storeId);
      session.bump();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [api, busy, session, simToday, storeId]);

  const select = useCallback(
    (id: string) => {
      if (id !== caseId) {
        session.setCaseId(id, storeId);
        session.bump();
      }
    },
    [caseId, session, storeId],
  );

  return { conversations, previews, busy, error, startNew, select };
}
