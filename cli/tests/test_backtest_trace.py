import json

from conftest import CASE
from glazed_cli.state import State

RUN = {
    "run_id": "r1", "case_id": "c1", "store_id": "S030", "period_from": "2026-03-01",
    "period_to": "2026-03-14", "policy": "default", "label": "backtest", "created_at": "2026-10-10T10:00:00Z",
    "results": {
        "label": "backtest", "days": 14, "note": "Estimates from a simple projection.",
        "waste_usd": {"current": 300.0, "policy": 100.0, "delta": -200.0},
        "lost_sales_usd": {"current": 200.0, "policy": 50.0, "delta": -150.0},
        "net_usd": {"current": 500.0, "policy": 150.0, "delta": -350.0},
        "daily": [{"date": "2026-03-01", "current": {"waste_usd": 1.0}, "policy": {"waste_usd": 0.5}}],
    },
}


def test_backtest_run_posts_to_current_case(api, run):
    State(current_case="c1").save()
    api.on("POST", "/api/v1/cases/c1/backtests", RUN, 201)
    r = run("backtest", "run", "--from", "2026-03-01", "--to", "2026-03-14", "--policy", "default")
    assert r.exit_code == 0, r.output
    assert api.last_json() == {"date_from": "2026-03-01", "date_to": "2026-03-14", "policy": "default"}
    assert "BACKTEST" in r.output and "r1" in r.output
    assert "100.00" in r.output and "300.00" in r.output
    assert "+350.00" in r.output  # net improvement vs current practice (lower net cost is better)
    assert "0.50" not in r.output  # the per-day detail is not dumped into the summary


def test_backtest_run_with_store_creates_backtest_case(api, run):
    api.on("POST", "/api/v1/cases", {**CASE, "case_id": "c7", "mode": "backtest"}, 201)
    api.on("POST", "/api/v1/cases/c7/backtests", RUN, 201)
    r = run("backtest", "run", "--store", "S030", "--from", "2026-03-01", "--to", "2026-03-14")
    assert r.exit_code == 0, r.output
    first = json.loads(api.calls[0].content)
    assert first == {"store_id": "S030", "sim_today": "2026-03-14", "mode": "backtest",
                     "title": "backtest S030 2026-03-01..2026-03-14"}
    assert State.load().current_case == "c7"
    assert "policy" not in json.loads(api.calls[1].content)


def test_backtest_show(api, run):
    api.on("GET", "/api/v1/backtests/r1", RUN)
    r = run("backtest", "show", "r1")
    assert "waste" in r.output.lower() and "lost sales" in r.output.lower() and "net" in r.output.lower()
    assert "current practice" in r.output.lower() and "backtest" in r.output.lower()


def test_backtest_show_without_baseline_still_renders(api, run):
    api.on("GET", "/api/v1/backtests/r2", {**RUN, "run_id": "r2",
           "results": {"waste_usd": {"current": 4.0, "policy": 1.0, "delta": -3.0}, "extra": "x"}})
    r = run("backtest", "show", "r2")
    assert r.exit_code == 0 and "4.00" in r.output and "1.00" in r.output


EVENTS = [
    {"event_id": "e1", "case_id": "c1", "store_id": "S030", "ts": "2026-10-10T10:00:01Z",
     "from_agent": "orchestrator", "to_agent": "present", "kind": "message", "payload": {"text": "sales?"}},
    {"event_id": "e2", "case_id": "c1", "store_id": "S030", "ts": "2026-10-10T10:00:02Z",
     "from_agent": "present", "to_agent": "backend", "kind": "tool_call",
     "payload": {"tool": "day_summary", "args": {"date": "2026-03-09"}, "pad": "x" * 300}},
]


def test_trace_current_case(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/trace", EVENTS)
    r = run("trace")
    q = api.last().url.params
    assert q["case_id"] == "c1" and "store_id" not in q
    assert "orchestrator" in r.output and "present" in r.output and "tool_call" in r.output
    assert "->" in r.output or "→" in r.output
    assert "x" * 200 not in r.output  # payload truncated


def test_trace_by_store_only(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/trace", [])
    r = run("trace", "--store", "S030")
    q = api.last().url.params
    assert q["store_id"] == "S030" and "case_id" not in q
    assert "No trace events" in r.output


def test_trace_json_raw(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/trace", EVENTS)
    r = run("--json", "trace")
    assert json.loads(r.output)[0]["event_id"] == "e1"


def test_agent_color_is_stable():
    from glazed_cli.render import agent_color
    assert agent_color("present") == agent_color("present")
    assert agent_color("present") != agent_color("supply")


def test_trace_follow_prints_only_new_events(api, run, monkeypatch):
    monkeypatch.setenv("GLAZED_FOLLOW_POLLS", "3")
    monkeypatch.setenv("GLAZED_FOLLOW_INTERVAL", "0")
    State(current_case="c1").save()
    api.seq("GET", "/api/v1/trace", [EVENTS[:1], EVENTS, EVENTS])
    r = run("trace", "-f")
    assert r.exit_code == 0, r.output
    assert r.output.count("sales?") == 1 and r.output.count("day_summary") == 1
    assert "10:00:01" in r.output and "orchestrator" in r.output and "present" in r.output
    assert api.last().url.params["case_id"] == "c1"


def test_trace_follow_all_store_uses_the_store(api, run, monkeypatch):
    monkeypatch.setenv("GLAZED_FOLLOW_POLLS", "1")
    State(current_case="c1").save()
    api.on("GET", "/api/v1/cases/c1", {**__import__("conftest").CASE})
    api.on("GET", "/api/v1/trace", EVENTS)
    r = run("trace", "--follow", "--all-store")
    assert r.exit_code == 0, r.output
    q = api.last().url.params
    assert q["store_id"] == "S030" and "case_id" not in q
