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
    description = op["x-agent-description"]
    assert op["x-agent-effect"] == effect
    # written for the model: a sentence or more, trimmed, no route or code path leaking into it
    assert description == description.strip() and len(description) >= 60
    assert description.split("\n")[0].endswith((".", ":")), "the first line is a sentence"
    assert PREFIX not in description and "/internal" not in description
    # and about THIS tool, not the operation's summary or another tool's text
    assert description != op.get("summary")


def test_no_two_tools_share_a_description(spec: dict[str, Any]) -> None:
    texts = {
        name: _operations(spec)[(m, p)]["x-agent-description"] for name, (m, p, _) in TOOLS.items()
    }
    duplicated = {n for n, t in texts.items() if list(texts.values()).count(t) > 1}
    assert duplicated == set()


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


def test_the_committed_snapshot_is_the_current_internal_contract() -> None:
    from scripts.export_internal_openapi import _current

    assert json.loads(SNAPSHOT.read_text(encoding="utf-8")) == _current()


def _served_app():  # type: ignore[no-untyped-def]
    from glazed_backend.adapters.driving.app import create_app
    from tests.unit.test_forecast_internal import make_container

    container = make_container()
    return container, create_app(container)


def test_the_served_document_offers_agent_core_the_operations_of_the_snapshot() -> None:
    """Agent-Core reads the SERVED `/openapi.json` (base_url + /openapi.json), not the snapshot. The
    served document names some schemas differently (a public model with the same name makes FastAPI
    qualify the internal one), so the check compares the internal operations with every `$ref`
    resolved: what the bridge builds tools from."""
    from scripts.export_internal_openapi import served_divergence

    _, app = _served_app()

    assert served_divergence(app.openapi(), json.loads(SNAPSHOT.read_text(encoding="utf-8"))) == []


def test_a_served_operation_that_differs_from_the_snapshot_is_named() -> None:
    from scripts.export_internal_openapi import served_divergence

    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    served = json.loads(json.dumps(snapshot))
    del served["paths"][PREFIX + "/kpis"]["get"]["x-agent-tool"]
    del served["paths"][PREFIX + "/staffing"]
    served["paths"][PREFIX + "/extra"] = {"get": {"responses": {}}}

    assert served_divergence(served, snapshot) == [
        PREFIX + "/extra",
        PREFIX + "/kpis",
        PREFIX + "/staffing",
    ]


def test_the_snapshot_does_not_move_when_only_the_public_api_changes() -> None:
    """G2b + gm2 advisory: the snapshot is built from the internal routes alone. A public model
    that COLLIDES with an internal schema name, a new public route and a renamed application all
    change the served document; neither the snapshot nor the internal operations Agent-Core sees
    move."""
    from pydantic import BaseModel

    from scripts.export_internal_openapi import internal_spec, served_divergence

    class PromoAuditBody(BaseModel):  # the name of an internal request body
        secret_public_field: str

    container, app = _served_app()
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    served_before = json.dumps(app.openapi(), sort_keys=True)
    app.add_api_route(
        "/api/v1/extra",
        lambda body: PromoAuditBody(secret_public_field="x"),
        methods=["POST"],
        response_model=PromoAuditBody,
    )
    app.title, app.version, app.openapi_schema = "renamed", "9.9.9", None
    served_after = app.openapi()

    # the change is real: the served document moved
    assert json.dumps(served_after, sort_keys=True) != served_before
    assert "/api/v1/extra" in served_after["paths"] and served_after["info"]["title"] == "renamed"
    assert "secret_public_field" in json.dumps(served_after)
    # ...and the internal contract did not
    assert internal_spec(container) == snapshot
    assert "secret_public_field" not in json.dumps(snapshot)
    assert served_divergence(served_after, snapshot) == []


def _snapshot() -> dict[str, Any]:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _served_diverges(monkeypatch, export) -> None:  # type: ignore[no-untyped-def]
    """`_current` is the committed snapshot and the served document differs from it at /kpis:
    no test builds the real application unless it means to (gm3 advisory, export:96)."""
    served = _snapshot()
    served["paths"][PREFIX + "/kpis"]["get"]["x-agent-name"] = "renamed_tool"
    monkeypatch.setattr(export, "_current", _snapshot)
    monkeypatch.setattr(export, "_served", lambda: served)


def test_check_mode_with_no_snapshot_fails_and_says_so(tmp_path: Path, monkeypatch, capsys) -> None:
    import scripts.export_internal_openapi as export

    monkeypatch.setattr(export, "SNAPSHOT", tmp_path / "absent" / "internal_openapi.json")
    _served_diverges(monkeypatch, export)

    assert export.main(["--check"]) == 1
    assert "missing" in capsys.readouterr().err
    assert not (tmp_path / "absent").exists(), "--check never writes"


def test_check_mode_reports_a_stale_snapshot_without_rewriting_it(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    import scripts.export_internal_openapi as export

    stale = tmp_path / "internal_openapi.json"
    stale.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(export, "SNAPSHOT", stale)
    _served_diverges(monkeypatch, export)

    assert export.main(["--check"]) == 1
    assert "stale" in capsys.readouterr().err
    assert stale.read_text(encoding="utf-8") == "{}\n"


def test_check_mode_fails_when_the_served_document_diverges(monkeypatch, capsys) -> None:
    import scripts.export_internal_openapi as export

    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    served = json.loads(json.dumps(snapshot))
    served["paths"][PREFIX + "/kpis"]["get"]["x-agent-name"] = "renamed_tool"
    monkeypatch.setattr(export, "_current", lambda: snapshot)
    monkeypatch.setattr(export, "_served", lambda: served)

    assert export.main(["--check"]) == 1
    err = capsys.readouterr().err
    assert "served" in err and PREFIX + "/kpis" in err


def test_check_mode_names_a_missing_or_stale_snapshot_before_any_served_divergence(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """gm3 advisory (export:94-102): the served comparison is made against the COMMITTED snapshot,
    so a snapshot that is missing or stale is reported as such, never as a served divergence."""
    import scripts.export_internal_openapi as export

    _served_diverges(monkeypatch, export)
    monkeypatch.setattr(export, "SNAPSHOT", tmp_path / "internal_openapi.json")

    assert export.main(["--check"]) == 1
    assert "missing" in capsys.readouterr().err
    (tmp_path / "internal_openapi.json").write_text("{}\n", encoding="utf-8")
    assert export.main(["--check"]) == 1
    err = capsys.readouterr().err
    assert "stale" in err and "served" not in err


def test_check_mode_passes_when_snapshot_and_served_document_agree(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    import scripts.export_internal_openapi as export

    current = tmp_path / "internal_openapi.json"
    current.write_text(SNAPSHOT.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(export, "SNAPSHOT", current)
    monkeypatch.setattr(export, "_current", _snapshot)
    monkeypatch.setattr(export, "_served", _snapshot)

    assert export.main(["--check"]) == 0
    assert capsys.readouterr().err == ""


def test_rewrite_mode_writes_the_snapshot_even_when_the_served_document_diverges(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """gm3 advisory (export:94-102): only `--check` compares with the served document (the module
    docstring). Rewrite mode regenerates the snapshot from the internal router and succeeds; it
    never reads the served document."""
    import scripts.export_internal_openapi as export

    target = tmp_path / "out" / "internal_openapi.json"
    monkeypatch.setattr(export, "SNAPSHOT", target)
    monkeypatch.setattr(export, "_current", _snapshot)

    def _served_is_not_read() -> dict[str, Any]:
        raise AssertionError("rewrite mode read the served document")

    monkeypatch.setattr(export, "_served", _served_is_not_read)

    assert export.main([]) == 0
    assert json.loads(target.read_text(encoding="utf-8")) == _snapshot()
    assert capsys.readouterr().err == ""


def _with_component(spec: dict[str, Any], name: str, schema: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(spec))
    out.setdefault("components", {}).setdefault("schemas", {})[name] = schema
    return out


def _one_operation(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "paths": {
            PREFIX + "/thing": {
                "get": {"responses": {"200": {"content": {"application/json": {"schema": schema}}}}}
            }
        }
    }


def test_a_ref_with_sibling_keys_resolves_whatever_the_schema_is_named() -> None:
    """gm3 advisory (export:50-55): FastAPI may qualify a schema's name in the served document, and
    a `$ref` can sit next to other keys (`description`). Resolved, both sides are the same."""
    from scripts.export_internal_openapi import served_divergence

    body = {"type": "object", "properties": {"qty": {"type": "integer"}}}
    snapshot = _with_component(
        _one_operation({"$ref": "#/components/schemas/Thing", "description": "the thing"}),
        "Thing",
        body,
    )
    served = _with_component(
        _one_operation({"$ref": "#/components/schemas/internal__Thing", "description": "the thing"}),
        "internal__Thing",
        body,
    )
    changed = _with_component(
        _one_operation({"$ref": "#/components/schemas/internal__Thing", "description": "other"}),
        "internal__Thing",
        body,
    )

    assert served_divergence(served, snapshot) == []
    assert served_divergence(changed, snapshot) == [PREFIX + "/thing"]


def test_a_self_referencing_schema_resolves_whatever_it_is_named() -> None:
    """A cycle is compared by its shape (how far up it points), not by the schema's name."""
    from scripts.export_internal_openapi import served_divergence

    def tree(name: str, leaf: str = "string") -> dict[str, Any]:
        node = {
            "type": "object",
            "properties": {
                "label": {"type": leaf},
                "children": {"type": "array", "items": {"$ref": f"#/components/schemas/{name}"}},
            },
        }
        return _with_component(_one_operation({"$ref": f"#/components/schemas/{name}"}), name, node)

    assert served_divergence(tree("internal__Node"), tree("Node")) == []
    assert served_divergence(tree("internal__Node", "integer"), tree("Node")) == [
        PREFIX + "/thing"
    ]
