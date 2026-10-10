"""Decision copilot (Wave 14). Everything the manager reads about an issue is computed here from the issue and its
options (themselves computed by glazed_metrics); no model produces a number. Text is Spanish, built from templates."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, time, timedelta, timezone
from typing import Any

from ..domain import Case, DomainError, NotFound
from ..domain.models import MEMORY_CATEGORIES
from ..metrics.analysis import build_analysis, usd  # noqa: F401  (usd is re-exported for the templates' callers)

MODES = ("analizar", "dialogo")
_INSTRUCTION = {"analizar": "Analyze this issue for the manager.",
                "dialogo": "Answer questions about this issue."}


def find_issue(alerts: Any, metrics: Any, served: dict, case: Case, issue_id: str) -> dict[str, Any] | None:
    """The issue as served to this case, else the alert's stored issue, else recomputed at the case date."""
    issue = served.get((case.case_id, issue_id))
    if issue is None:
        alert = alerts.get_by_issue_key(issue_id)
        issue = alert.issue if alert is not None and alert.store_id == case.store_id else None
    if issue is None or not issue.get("options"):
        pool = metrics.issues(case.store_id, case.sim_today, 10_000)
        issue = next((i for i in pool if i.get("issue_id") == issue_id), None) or \
            next((i for i in pool if issue_id in (i.get("merged_issue_ids") or [])), None)  # merged into another issue
    return issue


def require_issue(alerts: Any, metrics: Any, served: dict, case: Case, issue_id: str) -> dict[str, Any]:
    issue = find_issue(alerts, metrics, served, case, issue_id)
    if issue is None:
        raise NotFound(f"issue {issue_id!r} not found for case {case.case_id!r}")
    served[(case.case_id, issue_id)] = issue
    return issue


def _option_line(o: dict[str, Any]) -> dict[str, Any]:
    conf = o.get("confidence") or {}
    return {"option_id": o["option_id"], "action_type": o["action_type"], "params": o.get("params", {}),
            "net_usd_mid": o.get("net_usd_mid"), "cost_usd": o.get("cost_usd"), "tier": o.get("tier"),
            "confidence": conf.get("score"), "deadline": (o.get("urgency") or {}).get("deadline_date")}


def context_block(issue: dict[str, Any], option_id: str | None, mode: str) -> str:
    """The pinned block prepended to the manager's message: issue summary and options, all computed by code."""
    summary = {"issue_id": issue["issue_id"], "kind": issue.get("kind"), "sku": issue.get("sku"),
               "product_name": issue.get("product_name"), "supplier_id": issue.get("supplier_id"),
               "severity_usd": issue.get("severity_usd"), "recommended_option_id": issue.get("recommended_option_id"),
               "options": [_option_line(o) for o in issue.get("options", [])]}
    lines = ["[PINNED CONTEXT - computed by code; quote these numbers, never invent others]",
             f"Mode: {mode}. {_INSTRUCTION[mode]}"]
    if option_id:
        lines.append(f"Pinned option: {option_id}")
    lines += [json.dumps(summary, ensure_ascii=False, sort_keys=True), "[END PINNED CONTEXT]", "", ""]
    return "\n".join(lines)


def validate_context(issue: dict[str, Any], option_id: str | None, mode: str) -> None:
    if mode not in MODES:
        raise DomainError(f"mode must be one of {', '.join(MODES)}")
    if option_id and not any(o.get("option_id") == option_id for o in issue.get("options", [])):
        raise DomainError(f"unknown option {option_id!r} for issue {issue['issue_id']!r}")


ANALYSIS_SOURCE = "issues+options (glazed_metrics_v1)"


class IssueAnalysis:
    def __init__(self, cases: Any, alerts: Any, metrics: Any, served: dict, names: Any) -> None:
        self.cases, self.alerts, self.metrics, self.served, self.names = cases, alerts, metrics, served, names

    def execute(self, case: Case, issue_id: str) -> dict[str, Any]:
        issue = require_issue(self.alerts, self.metrics, self.served, case, issue_id)
        return {"as_of": case.sim_today.isoformat(), "store_id": case.store_id,
                "store_display_name": self.names.of(case.store_id), "source": ANALYSIS_SOURCE, **build_analysis(issue)}


def _dedupe_by_sku_action(approvals: list[dict[str, Any]], technical: list[dict[str, Any]]) -> tuple[list, list]:
    """The same SKU never shows in approvals and technical with the same action: the technical / order-plan item stays
    and links the issue (`linked_issue_ids`); a technical-from-issue duplicate of a plan line is folded into the line."""
    def act(x: dict[str, Any]) -> str:
        return (x.get("recommendation") or {}).get("action_type") or x.get("action_type") or "place_order"

    first: dict[tuple, dict[str, Any]] = {}
    kept_tech = []
    for t in technical:
        key = (t.get("sku"), act(t))
        if t.get("sku") and key in first:
            first[key].setdefault("linked_issue_ids", []).append(t["issue_id"])
            continue
        first.setdefault(key, t)
        kept_tech.append(t)
    kept = []
    for a in approvals:
        t = first.get((a.get("sku"), act(a)))
        if a.get("sku") and t is not None:
            t.setdefault("linked_issue_ids", []).append(a["issue_id"])
            continue
        kept.append(a)
    return kept, kept_tech


class PendingDecisions:
    """The manager inbox of one case: approvals (N2/N3) and technical items, minus what was already decided here."""

    SOURCE = "issues+order_plan+decisions (glazed_metrics_v1)"

    def __init__(self, metrics: Any, proposals: Any, served: dict, names: Any) -> None:
        self.metrics, self.proposals, self.served, self.names = metrics, proposals, served, names

    def items(self, case: Case) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        from ..metrics.pending import approval_item, technical_from_issue, technical_from_line
        decided = {p.issue_id for p in self.proposals.list(case_id=case.case_id) if p.status in ("approved", "rejected")}

        def done(issue: dict[str, Any]) -> bool:  # deciding the primary resolves the merged ones (and the reverse)
            return issue["issue_id"] in decided or any(m in decided for m in issue.get("merged_issue_ids") or [])

        plan = self.metrics.order_plan(case.store_id, case.sim_today)
        technical, in_plan = [], set()
        for line in plan.get("lines", []):
            issue = line.get("issue") if isinstance(line.get("issue"), dict) else None
            if issue:
                self.served[(case.case_id, issue["issue_id"])] = issue
                in_plan.add(issue["issue_id"])
                if done(issue):
                    continue
            technical.append(technical_from_line(line, issue))
        approvals = []
        for issue in self.metrics.issues(case.store_id, case.sim_today, 10_000):
            iid = issue["issue_id"]
            if issue.get("category") == "integrity" or done(issue) or iid in in_plan:
                continue
            self.served[(case.case_id, iid)] = issue
            item = approval_item(issue)
            if item is not None:
                approvals.append(item)
                continue
            tech = technical_from_issue(issue)
            if tech is not None:
                technical.append(tech)
        approvals, technical = _dedupe_by_sku_action(approvals, technical)
        approvals.sort(key=lambda a: (-a["impact_usd"]["mid"], a["issue_id"]))
        return approvals, technical

    def execute(self, case: Case) -> dict[str, Any]:
        approvals, technical = self.items(case)
        return {"as_of": case.sim_today.isoformat(), "store_id": case.store_id,
                "store_display_name": self.names.of(case.store_id), "source": self.SOURCE,
                "approvals": approvals, "technical": technical}


class RecordDecision:
    """Proposal + decision in one call. The proposal comes from the option (action, params and tier are copied from
    code); a pending proposal an agent already made for the same option is reused. An Idempotency-Key replays the
    original outcome and never decides twice."""

    def __init__(self, cases: Any, proposals: Any, executions: Any, alerts: Any, metrics: Any, served: dict,
                 memory: Any = None, classifier: Any = None, decision_memories: Any = None, clock: Any = None) -> None:
        self.cases, self.proposals, self.executions, self.alerts = cases, proposals, executions, alerts
        self.metrics, self.served, self.memory, self.classifier = metrics, served, memory, classifier
        self.decision_memories, self.clock = decision_memories, clock

    @staticmethod
    def _out(p: Any, replay: bool) -> dict[str, Any]:
        out = {"decision_id": p.proposal_id, "proposal_id": p.proposal_id, "status": p.status}
        if p.reason_category:
            out["reason_category"] = p.reason_category
        if replay:
            out["idempotent_replay"] = True
        return out

    def execute(self, case_id: str, issue_id: str, option_id: str, approved: bool, reason: str = "",
                idempotency_key: str | None = None) -> tuple[dict[str, Any], bool]:
        from . import DecideProposal, ProposeOption, _case
        from ..domain import InvalidTransition
        case = _case(self.cases, case_id)
        if idempotency_key:
            prior = self.proposals.find_by_idempotency_key(case.case_id, idempotency_key)
            if prior is not None and prior.status != "pending":
                return self._out(prior, True), False
        issue = require_issue(self.alerts, self.metrics, self.served, case, issue_id)
        if not any(o.get("option_id") == option_id for o in issue["options"]):
            raise DomainError(f"unknown option {option_id!r} for issue {issue_id!r}")
        if not approved and not reason.strip():
            raise DomainError("a reason is required to reject a proposal")
        mine = [p for p in self.proposals.list(case_id=case.case_id)
                if p.issue_id == issue_id and (p.params or {}).get("option_id") == option_id]
        if any(p.status != "pending" for p in mine):
            raise InvalidTransition(f"option {option_id!r} of issue {issue_id!r} was already decided in this case")
        proposal = next((p for p in mine if p.status == "pending"), None)
        if proposal is None:
            proposal, _ = ProposeOption(self.cases, self.proposals, self.alerts, self.metrics, self.served).execute_keyed(
                case.case_id, issue_id, option_id, "Decided by the manager", idempotency_key=idempotency_key)
        DecideProposal(self.cases, self.proposals, self.executions, self.alerts, self.memory, self.classifier,
                       self.decision_memories, self.clock).execute(
            proposal.proposal_id, approved, reason, issue.get("product_name") or issue.get("sku"))
        return self._out(self.proposals.get(proposal.proposal_id), False), True


class ListMemories:
    """What the copilot has learned about this store, newest first. Sources: approved decisions (decision log), the
    store's Backboard experiences, the preferences kept from rejection reasons and the measured outcomes of decisions.
    Items are dated by the simulated day they belong to (never the wall clock); decisions of archived or later
    cases and anything dated after this case's date are never shown. Categories come from `memory_view.category_of`."""

    SOURCES = ("decision_log", "backboard", "rejection_reason", "outcome")
    NEW_FOR = timedelta(hours=24)

    def __init__(self, cases: Any, proposals: Any, metrics: Any, memory: Any, decision_memories: Any, clock: Any) -> None:
        self.cases, self.proposals, self.metrics = cases, proposals, metrics
        self.memory, self.decision_memories, self.clock = memory, decision_memories, clock

    def execute(self, case: Case, category: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
        from ..metrics.memory_view import action_in_text, approved_text, category_of, valid_category
        from .scope import decision_date, experience_visible, in_scope
        if not valid_category(category):
            raise DomainError(f"category must be one of {', '.join(MEMORY_CATEGORIES)}")
        store = case.store_id
        owners = {c.case_id: c for c in self.cases.list(store)}
        catalog = self.metrics.product_catalog(store) if hasattr(self.metrics, "product_catalog") else {}
        props = {p.proposal_id: p for p in self.proposals.list(store_id=store) if in_scope(case, p.case_id, owners)}
        seen = lambda d: d is None or d <= case.sim_today  # noqa: E731 - nothing dated after this case's day
        rows: list[dict[str, Any]] = []
        for p in props.values():
            day = decision_date(p, owners)
            if p.status != "approved" or not seen(day):
                continue
            parts = p.issue_id.split("|")
            sku = p.params.get("sku")
            supplier = p.params.get("supplier_name") or p.params.get("supplier_id") or (parts[2] if len(parts) > 2 and not sku else None)
            product = (catalog.get(sku) or {}).get("product_name") or sku or (f"el proveedor {supplier}" if supplier else "la tienda")
            rows.append(self._row(f"dec-{p.proposal_id}", category_of(p.action_type, None, parts[1] if len(parts) > 2 else None),
                                  approved_text(p.action_type, product, p.params.get("decision_as_of")), "decision_log", True,
                                  day, p.created_at, (p.action_type, sku or p.params.get("supplier_id")), p.case_id))
        for m in self.decision_memories.list(store):
            if not in_scope(case, m.case_id, owners):
                continue
            own = props.get(m.decision_id)
            day = m.sim_date or (decision_date(own, owners) if own is not None else None) or \
                (owners[m.case_id].sim_today if m.case_id in owners else None)
            if not seen(day):
                continue
            outcome, note = m.memory_id.startswith("out-"), m.memory_id.startswith("note-")
            if note:  # a manager note: his own words, verified by definition
                rows.append(self._row(m.memory_id, m.category, m.text, "gerente", True, day, m.created_at,
                                      ("nota", m.text), m.case_id))
                continue
            rows.append(self._row(m.memory_id, m.category, m.text, "outcome" if outcome else "rejection_reason", outcome, day,
                                  m.created_at, (m.action_type, m.sku if outcome else (m.reason_category or "otro")), m.case_id))
        own_outcomes = {r["text"] for r in rows if r["source"] == "outcome"}
        for e in self._experiences(store):
            if e.kind == "outcome" and e.text in own_outcomes:
                continue  # the same fact as the verified outcome memory
            if e.kind == "note" and (e.ref or "").startswith("note-"):
                continue  # the local manager-note row is the scope-aware copy of this fact
            if not experience_visible(case, e, self.proposals, owners):
                continue
            local = props.get(e.decision_id or "")
            if local is not None and e.kind == "decision":
                continue  # the same fact as the decision log / rejection memory
            action = (local.action_type if local else None) or action_in_text(e.text)
            cat = "demanda" if e.kind == "promo_evaluation" else category_of(action)
            day = decision_date(local, owners) if local is not None else None
            rows.append(self._row("bb-" + hashlib.sha1(f"{e.kind}|{e.decision_id}|{e.text}".encode()).hexdigest()[:12], cat,
                                  e.text, "backboard", bool(local), day, e.created_at, (action, e.ref or e.decision_id),
                                  local.case_id if local else None))
        holders: dict[tuple, set[str]] = {}
        for r in rows:  # cases_count: distinct cases holding a memory of the same category and pattern
            holders.setdefault((r["category"], r["_key"]), set()).add(r["_case"])
        for r in rows:
            r["cases_count"] = len(holders[(r["category"], r.pop("_key"))] - {None}) or 1
            r.pop("_case")
        rows.sort(key=lambda r: (r["created_at"], r["recorded_at"]), reverse=True)  # newest first, ties by write time
        return [r for r in rows if (category is None or r["category"] == category) and (not q or q.lower() in r["text"].lower())]

    def _experiences(self, store_id: str) -> list[Any]:
        if self.memory is None:
            return []
        try:
            return list(self.memory.recall(store_id, "", 50))
        except Exception:  # noqa: BLE001 - memory problems degrade to "no experiences"
            return []

    def _row(self, memory_id: str, category: str, text: str, source: str, verified: bool, day: Any, recorded_at: Any,
             key: tuple, case_id: str | None) -> dict[str, Any]:
        """`created_at` is the simulated day the memory belongs to; `new` reads the moment it was recorded."""
        at = datetime.combine(day, time.min, tzinfo=timezone.utc) if day is not None else recorded_at
        return {"memory_id": memory_id, "category": category, "text": text, "source": source, "cases_count": 1,
                "verified": verified, "created_at": at.isoformat(), "recorded_at": recorded_at.isoformat(),
                "new": self.clock.now() - recorded_at < self.NEW_FOR, "_key": key, "_case": case_id}


class AgentsStatus:
    """Is the Agent-Core reachable, and so are its agents? The Core has no per-agent health route, so every agent
    shares the Core's state: up (reachable, answered fast), degraded (slower than SLOW_MS) or down (unreachable).
    The probe has a short timeout and its answer is cached for about CACHE_S seconds."""

    CACHE_S, SLOW_MS = 15.0, 2000.0

    def __init__(self, core_of: Any, clock: Any) -> None:
        self.core_of, self.clock = core_of, clock
        self._at: Any = None
        self._cached: dict[str, Any] | None = None

    def execute(self) -> dict[str, Any]:
        from ..domain.models import AGENT_IDS
        from .reply_sanitizer import role_name_es
        now = self.clock.now()
        if self._cached is None or self._at is None or (now - self._at).total_seconds() >= self.CACHE_S:
            try:
                got = self.core_of().health()
                connected = bool(got.get("ok"))
                state = ("degraded" if float(got.get("latency_ms") or 0) > self.SLOW_MS else "up") if connected else "down"
            except Exception:  # noqa: BLE001 - unreachable, not configured or broken: all down
                connected, state = False, "down"
            self._cached = {"connected": connected, "agents": [
                {"agent_id": a, "display_name_es": role_name_es(a), "status": state}
                for a in AGENT_IDS]}
            self._at = now
        return self._cached


class InboxCounts:
    """Badges of the manager inbox: pending approvals, pending technical items and open alerts of this case."""

    OPEN = ("nueva", "vista", "en_analisis")

    def __init__(self, pending: PendingDecisions, alerts: Any) -> None:
        self.pending, self.alerts = pending, alerts

    def execute(self, case: Case) -> dict[str, int]:
        approvals, technical = self.pending.items(case)
        open_alerts = [a for a in self.alerts.list(case.store_id) if a.state.value in self.OPEN]  # alerts live on their own issue cases: count the store inbox
        return {"approvals": len(approvals), "technical": len(technical), "alerts": len(open_alerts)}
