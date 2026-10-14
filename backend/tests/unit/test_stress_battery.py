"""Pure parts of the stress battery (scripts/stress/battery.py): case loading, quality checks, trace metrics,
aggregates, compare and the Markdown summary. No network, no backend."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

STRESS = Path(__file__).resolve().parents[3] / "scripts" / "stress"
sys.path.insert(0, str(STRESS))

import battery  # noqa: E402


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "cases.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _battery(**over) -> dict:
    base = {"version": 1, "store_id": "S001", "sim_today": "2026-07-19", "mode": "sandbox",
            "cases": [{"id": "simple", "kind": "simple", "turns": ["Hola, ¿cómo vamos hoy?"]}]}
    base.update(over)
    return base


# ---- case loading ----

def test_the_committed_case_file_loads_and_covers_every_required_kind():
    b = battery.load_cases(STRESS / "cases.json")
    kinds = {c.kind for c in b.cases}
    assert {"simple", "intent", "specialist", "multi_specialist", "proposal", "unsupported",
            "follow_up", "burst"} <= kinds
    intents = {c.expect.get("intent") for c in b.cases if c.kind == "intent"}
    assert intents == set(battery.FREQUENT_INTENTS)
    assert 20 <= sum(len(c.turns) for c in b.cases) <= 30
    assert next(c for c in b.cases if c.kind == "follow_up").turns.__len__() == 3
    assert len(next(c for c in b.cases if c.kind == "burst").turns) == 5
    assert b.mode == "sandbox"


def test_loading_rejects_duplicate_ids(tmp_path):
    case = {"id": "a", "kind": "simple", "turns": ["x"]}
    with pytest.raises(battery.BatteryError, match="duplicate case id 'a'"):
        battery.load_cases(_write(tmp_path, _battery(cases=[case, case])))


def test_loading_rejects_unknown_kind_and_empty_turns(tmp_path):
    with pytest.raises(battery.BatteryError, match="unknown kind 'magic'"):
        battery.load_cases(_write(tmp_path, _battery(cases=[{"id": "a", "kind": "magic", "turns": ["x"]}])))
    with pytest.raises(battery.BatteryError, match="case 'a' has no turns"):
        battery.load_cases(_write(tmp_path, _battery(cases=[{"id": "a", "kind": "simple", "turns": []}])))


def test_loading_rejects_a_live_mode_battery(tmp_path):
    with pytest.raises(battery.BatteryError, match="mode must be 'sandbox'"):
        battery.load_cases(_write(tmp_path, _battery(mode="live")))


# ---- quality checks ----

def test_a_clean_spanish_reply_with_traceable_numbers_has_no_flags():
    q = battery.quality("Hoy vendiste 1,234.50 USD y tienes 3 alertas abiertas.",
                        tool_results=['{"net_sales": 1234.5, "open": 3}'])
    assert q["flags"] == []
    assert q["numbers_checked"] == 2 and q["untraceable_numbers"] == []


def test_think_tags_garbled_runs_and_foreign_scripts_are_flagged():
    q = battery.quality("<think>calculo</think> Las ventas суть buenas 销售 hoy.", tool_results=[])
    assert {"think_tags", "foreign_script"} <= set(q["flags"])


def test_an_english_reply_is_flagged_non_spanish():
    q = battery.quality("The sales today are good and the store is on track with the plan for the week.",
                        tool_results=[])
    assert "non_spanish" in q["flags"]


def test_internal_agent_tool_and_field_names_are_flagged():
    q = battery.quality("Le pregunté a glazed_supply con get_order_plan y el option_id indica pedir.", tool_results=[])
    assert "internal_names" in q["flags"]
    assert {"glazed_supply", "get_order_plan", "option_id"} <= set(q["internal_names"])


def test_sku_codes_and_dates_are_not_internal_names_nor_checked_numbers():
    q = battery.quality("El SKU-100502 llega el 2026-07-21 a las 10:30.", tool_results=[])
    assert q["internal_names"] == [] and q["numbers_checked"] == 0


def test_numbers_absent_from_the_tool_results_are_untraceable():
    q = battery.quality("Te recomiendo pedir 47 unidades; el costo es 812.40.",
                        tool_results=['{"qty": 20, "cost": 812.4}'])
    assert q["untraceable_numbers"] == ["47"]
    assert "untraceable_numbers" in q["flags"]


def test_small_counts_and_percent_rounding_are_tolerated():
    q = battery.quality("Hay 2 entregas y la merma es 12.3%.", tool_results=['{"waste_pct": 0.1234}'])
    assert q["untraceable_numbers"] == []


def test_refusal_detection():
    assert battery.looks_like_refusal("No tengo datos del clima para esa fecha, no puedo responder eso.")
    assert not battery.looks_like_refusal("Las ventas de hoy fueron 1,200 USD.")


# ---- trace metrics ----

def test_trace_metrics_count_only_this_turn_tool_calls_and_peer_asks():
    events = [
        {"kind": "tool", "payload": {"core_kind": "tool_call", "turn_id": "t1", "tool": "get_briefing"}},
        {"kind": "tool", "payload": {"core_kind": "tool_result", "turn_id": "t1", "tool": "get_briefing",
                                     "result": '{"sales": 10}'}},
        {"kind": "tool", "payload": {"core_kind": "tool_call", "turn_id": "t1", "tool": "ask_peer",
                                     "args": {"agent_id": "glazed_supply"}}},
        {"kind": "message", "payload": {"core_kind": "peer_exchange", "turn_id": "t1", "text": "¿pedido?"}},
        {"kind": "tool", "payload": {"core_kind": "tool_call", "turn_id": "t0", "tool": "get_issues"}},
    ]
    m = battery.trace_metrics(events, "t1")
    assert m["tool_calls"] == 2
    assert m["peer_asks"] == 1
    assert m["tools"] == {"get_briefing": 1, "ask_peer": 1}
    assert m["peers"] == ["glazed_supply"]
    assert m["tool_results"] == ['{"sales": 10}']


# ---- aggregates / compare / markdown ----

def _turn(case, latency, status="done", flags=(), burst=False, tools=2, peers=0):
    return {"case_id": case, "turn_index": 0, "status": status, "latency_s": latency, "burst": burst,
            "tool_calls": tools, "peer_asks": peers, "quality": {"flags": list(flags)}, "checks": {}}


def test_percentile_is_nearest_rank():
    assert battery.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50) == 5
    assert battery.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert battery.percentile([], 50) is None


def test_aggregate_reports_latency_failures_flags_and_burst():
    turns = [_turn("a", 10), _turn("b", 20, flags=["non_spanish"]), _turn("c", 30, status="failed"),
             _turn("burst", 40, burst=True), _turn("burst", 60, burst=True)]
    agg = battery.aggregate(turns)
    assert agg["turns"] == 5
    assert agg["failure_rate"] == 0.2
    assert agg["latency_p50_s"] == 30 and agg["latency_p95_s"] == 60
    assert agg["flag_counts"] == {"non_spanish": 1}
    assert agg["burst"] == {"turns": 2, "failed": 0, "latency_max_s": 60, "latency_p50_s": 40}
    assert agg["tool_calls_total"] == 10


def test_compare_pairs_turns_by_case_and_index_and_reports_deltas():
    before = {"label": "baseline", "turns": [_turn("a", 100), _turn("b", 50)], "aggregate": battery.aggregate(
        [_turn("a", 100), _turn("b", 50)])}
    after_turns = [_turn("a", 40), _turn("b", 55, flags=["internal_names"])]
    after = {"label": "phase3", "turns": after_turns, "aggregate": battery.aggregate(after_turns)}
    cmp = battery.compare(before, after)
    rows = {r["case_id"]: r for r in cmp["rows"]}
    assert rows["a"]["latency_delta_s"] == -60
    assert rows["b"]["new_flags"] == ["internal_names"]
    assert cmp["aggregate"]["latency_p50_s"] == {"before": 50, "after": 40, "delta": -10}
    md = battery.render_compare_markdown(cmp)
    assert "baseline" in md and "phase3" in md and "| a |" in md


def test_render_markdown_has_a_row_per_turn_and_the_aggregates():
    turns = [_turn("simple", 12.5, flags=["non_spanish"])]
    run = {"label": "baseline", "started_at": "2026-10-14T10:00:00Z", "store_id": "S001", "sim_today": "2026-07-19",
           "turns": turns, "aggregate": battery.aggregate(turns), "llm_calls_estimate": 3}
    md = battery.render_markdown(run)
    assert "| simple | 0 | done | 12.5 |" in md
    assert "non_spanish" in md
    assert "p50" in md


def test_tool_calls_without_results_make_the_sources_incomplete():
    events = [{"kind": "tool_call", "payload": {"core_kind": "tool_call", "turn_id": "t1", "tool": "get_briefing"}},
              {"kind": "tool_call", "payload": {"tool": "briefing", "text": "briefing"}}]  # backend mark: no turn
    m = battery.trace_metrics(events, "t1")
    assert m["tool_calls"] == 1 and m["results_complete"] is False


def test_incomplete_sources_report_unverified_numbers_without_the_flag():
    q = battery.quality("Vendiste 4,321 USD.", tool_results=[], complete=False)
    assert q["flags"] == [] and q["unverified_numbers"] == ["4,321"] and q["untraceable_numbers"] == []
