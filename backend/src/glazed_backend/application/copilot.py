"""Decision copilot (Wave 14). Everything the manager reads about an issue is computed here from the issue and its
options (themselves computed by glazed_metrics); no model produces a number. Text is Spanish, built from templates."""
from __future__ import annotations

import json
from typing import Any

from ..domain import Case, DomainError, NotFound
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
        issue = next((i for i in metrics.issues(case.store_id, case.sim_today, 1000) if i.get("issue_id") == issue_id), None)
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


class PendingDecisions:
    """The manager inbox of one case: approvals (N2/N3) and technical items, minus what was already decided here."""

    SOURCE = "issues+order_plan+decisions (glazed_metrics_v1)"

    def __init__(self, metrics: Any, proposals: Any, served: dict, names: Any) -> None:
        self.metrics, self.proposals, self.served, self.names = metrics, proposals, served, names

    def items(self, case: Case) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        from ..metrics.pending import approval_item, technical_from_issue, technical_from_line
        decided = {p.issue_id for p in self.proposals.list(case_id=case.case_id) if p.status in ("approved", "rejected")}
        plan = self.metrics.order_plan(case.store_id, case.sim_today)
        technical, in_plan = [], set()
        for line in plan.get("lines", []):
            issue = line.get("issue") if isinstance(line.get("issue"), dict) else None
            if issue:
                self.served[(case.case_id, issue["issue_id"])] = issue
                in_plan.add(issue["issue_id"])
                if issue["issue_id"] in decided:
                    continue
            technical.append(technical_from_line(line, issue))
        approvals = []
        for issue in self.metrics.issues(case.store_id, case.sim_today, 10_000):
            iid = issue["issue_id"]
            if issue.get("category") == "integrity" or iid in decided or iid in in_plan:
                continue
            self.served[(case.case_id, iid)] = issue
            item = approval_item(issue)
            if item is not None:
                approvals.append(item)
                continue
            tech = technical_from_issue(issue)
            if tech is not None:
                technical.append(tech)
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
                 memory: Any = None, classifier: Any = None, rejections: Any = None, clock: Any = None) -> None:
        self.cases, self.proposals, self.executions, self.alerts = cases, proposals, executions, alerts
        self.metrics, self.served, self.memory, self.classifier = metrics, served, memory, classifier
        self.rejections, self.clock = rejections, clock

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
        DecideProposal(self.cases, self.proposals, self.executions, self.alerts, self.memory, self.classifier).execute(
            proposal.proposal_id, approved, reason)
        decided = self.proposals.get(proposal.proposal_id)
        if not approved and self.rejections is not None:
            self.rejections.remember_rejection(case, decided, issue)
        return self._out(decided, False), True
