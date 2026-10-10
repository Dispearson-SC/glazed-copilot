"""Decision copilot (Wave 14). Everything the manager reads about an issue is computed here from the issue and its
options (themselves computed by glazed_metrics); no model produces a number. Text is Spanish, built from templates."""
from __future__ import annotations

import json
from typing import Any

from ..domain import Case, DomainError, NotFound

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
