import json

from conftest import CASE
from glazed_cli.state import State

CHILD = {**CASE, "case_id": "c2", "parent_case_id": "c1", "title": "what-if"}


def test_stores_lists_table(api, run):
    api.on("GET", "/api/v1/stores", [
        {"store_id": "S030", "name": "Saltillo Centro", "format": "mall", "site_id": "X1", "region": "Norte"}])
    r = run("stores")
    assert r.exit_code == 0, r.output
    assert "S030" in r.output and "Saltillo Centro" in r.output


def test_json_flag_prints_raw(api, run):
    api.on("GET", "/api/v1/stores", [{"store_id": "S030"}])
    r = run("--json", "stores")
    assert json.loads(r.output) == [{"store_id": "S030"}]


def test_case_new_posts_and_sets_current(api, run):
    api.on("POST", "/api/v1/cases", CASE, 201)
    r = run("case", "new", "--store", "S030", "--date", "2026-03-10", "--mode", "sandbox", "--title", "t")
    assert r.exit_code == 0, r.output
    assert api.last().method == "POST" and api.last().url.path == "/api/v1/cases"
    assert api.last_json() == {"store_id": "S030", "sim_today": "2026-03-10", "mode": "sandbox", "title": "t"}
    assert State.load().current_case == "c1"
    assert "c1" in r.output


def test_case_new_defaults_mode_live_and_omits_title(api, run):
    api.on("POST", "/api/v1/cases", CASE, 201)
    run("case", "new", "--store", "S030", "--date", "2026-03-10")
    assert api.last_json() == {"store_id": "S030", "sim_today": "2026-03-10", "mode": "live"}


def test_case_list_marks_current(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/cases", [CASE, CHILD])
    r = run("case", "list", "--store", "S030")
    assert api.last().url.params["store_id"] == "S030"
    lines = [ln for ln in r.output.splitlines() if "c1" in ln]
    assert lines and "*" in lines[0]


def test_case_use_validates_then_saves(api, run):
    api.on("GET", "/api/v1/cases/c2", CHILD)
    r = run("case", "use", "c2")
    assert r.exit_code == 0
    assert State.load().current_case == "c2"


def test_case_use_unknown_keeps_state(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/cases/zz", {"detail": "case not found"}, 404)
    r = run("case", "use", "zz")
    assert r.exit_code == 1 and "case not found" in r.output
    assert State.load().current_case == "c1"


def test_case_show_current(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/cases/c1", CASE)
    r = run("case", "show")
    assert "S030" in r.output and "2026-03-10" in r.output and "live" in r.output


def test_case_show_without_current_is_friendly(api, run):
    r = run("case", "show")
    assert r.exit_code == 1
    assert "case new" in r.output and "Traceback" not in r.output


def test_case_fork_switches_to_child(api, run):
    State(current_case="c1").save()
    api.on("POST", "/api/v1/cases/c1/fork", CHILD, 201)
    r = run("case", "fork", "--title", "what-if")
    assert api.last_json() == {"title": "what-if"}
    assert State.load().current_case == "c2"
    assert "c1" in r.output and "c2" in r.output


def test_backend_down_one_line(monkeypatch, api, run):
    import httpx

    from glazed_cli import client

    def boom(req):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(client, "TRANSPORT", httpx.MockTransport(boom))
    r = run("stores")
    assert r.exit_code == 1
    assert "Cannot reach the backend at http://backend.test" in r.output
    assert "Traceback" not in r.output and len(r.output.strip().splitlines()) == 1


def test_api_flag_overrides_url(api, run):
    api.on("GET", "/api/v1/stores", [])
    run("--api", "http://other.test", "stores")
    assert api.last().url.host == "other.test"
