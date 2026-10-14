"""OpenAPI marks on the internal API: the contract Agent-Core builds its tools from (D85, G2).

Only metadata: the marks (`x-agent-*`) say which /internal/v1 operations an agent tool calls and how
the model may see them. A route is a tool only when it is marked; the public API is never marked.
`tests/fixtures/internal_openapi.json` is the snapshot Agent-Core's tests build the glazed tools
from; regenerate it with `python backend/scripts/export_internal_openapi.py` after a deliberate change.
"""
import json
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_forecast_internal import build

SNAPSHOT = Path(__file__).resolve().parents[1] / "fixtures" / "internal_openapi.json"
PREFIX = "/internal/v1"

# tool name -> (method, path, effect)
TOOLS: dict[str, tuple[str, str, str]] = {
    "get_kpis": ("get", "/kpis", "read"),
    "get_snapshot": ("get", "/snapshot", "read"),
    "get_briefing": ("get", "/briefing", "read"),
    "get_day_summary": ("get", "/day-summary", "read"),
    "get_issues": ("get", "/issues", "read"),
    "explain_metric": ("get", "/metrics/explain", "read"),
    "get_order_plan": ("get", "/order-plan", "read"),
    "project_inventory": ("get", "/inventory/projection", "read"),
    "forecast_demand": ("get", "/forecast/demand", "read"),
    "forecast_daily_flow": ("get", "/forecast/flow", "read"),
    "get_supplier_performance": ("get", "/suppliers/performance", "read"),
    "get_history": ("get", "/history", "read"),
    "evaluate_promo": ("get", "/promos/{promo_id}/evaluation", "read"),
    "recall_experiences": ("get", "/experiences", "read"),
    "check_compliance": ("get", "/compliance", "read"),
    "get_transfer_options": ("get", "/transfers/options", "read"),
    "get_inventory_status": ("get", "/inventory", "read"),
    "get_expiring": ("get", "/expiring", "read"),
    "get_deliveries": ("get", "/deliveries", "read"),
    "get_staffing": ("get", "/staffing", "read"),
    "get_promos": ("get", "/promos", "read"),
    "get_outlook": ("get", "/outlook", "read"),
    "get_issue_analysis": ("get", "/issues/{issue_id}/analysis", "read"),
    "audit_promo": ("post", "/promos/audit", "read"),
    "classify_text": ("post", "/classify", "read"),
    "record_event": ("post", "/events", "write"),
    "propose_action": ("post", "/proposals", "write"),
    "save_manager_note": ("post", "/notes", "write"),
    "propose_transfer": ("post", "/transfers/proposals", "write"),
}
# internal operations that are NOT agent tools (the series route has no tool)
UNMARKED = {("get", "/forecast")}


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    client, _ = build()
    return client.get("/openapi.json").json()


def _operations(spec: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (method, path.removeprefix(PREFIX)): op
        for path, item in spec["paths"].items()
        if path.startswith(PREFIX)
        for method, op in item.items()
    }


def test_exactly_the_agent_tools_are_marked_and_nothing_public(spec: dict[str, Any]) -> None:
    marked = {
        (m, p): op["x-agent-name"]
        for (m, p), op in _operations(spec).items()
        if op.get("x-agent-tool") is True
    }
    assert marked == {(m, p): name for name, (m, p, _) in TOOLS.items()}
    public = [
        (path, method)
        for path, item in spec["paths"].items()
        if not path.startswith(PREFIX)
        for method, op in item.items()
        if any(key.startswith("x-agent") for key in op)
    ]
    assert public == []


def test_every_internal_operation_is_either_a_tool_or_deliberately_not(spec: dict[str, Any]) -> None:
    unmarked = {k for k, op in _operations(spec).items() if not op.get("x-agent-tool")}
    assert unmarked == UNMARKED


@pytest.mark.parametrize("name", sorted(TOOLS))
def test_a_tool_has_its_effect_and_a_description_the_model_reads(
    spec: dict[str, Any], name: str
) -> None:
    method, path, effect = TOOLS[name]
    op = _operations(spec)[(method, path)]
    assert op["x-agent-effect"] == effect
    assert len(op["x-agent-description"]) > 20


def test_writes_that_create_a_proposal_key_their_retries(spec: dict[str, Any]) -> None:
    ops = _operations(spec)
    assert ops[("post", "/proposals")]["x-agent-idempotency"] == ["issue_id", "option_id"]
    assert ops[("post", "/transfers/proposals")]["x-agent-idempotency"] == ["option_id"]
    others = [
        name
        for name, (m, p, _) in TOOLS.items()
        if "x-agent-idempotency" in ops[(m, p)] and name not in ("propose_action", "propose_transfer")
    ]
    assert others == []


def test_memory_recall_surfaces_the_warning_header(spec: dict[str, Any]) -> None:
    op = _operations(spec)[("get", "/experiences")]
    assert op["x-agent-warning"] is True


def test_the_committed_snapshot_is_the_current_internal_contract(spec: dict[str, Any]) -> None:
    from scripts.export_internal_openapi import internal_contract

    assert json.loads(SNAPSHOT.read_text(encoding="utf-8")) == internal_contract(spec)
