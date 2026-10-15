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


# ---- L13 false positives ----

def test_two_spanish_words_joined_by_an_underscore_are_a_typo_not_an_internal_name():
    """L13: the phase3 run flagged `de_no` ("problema de_no poder surtir"): a model typo joining two Spanish
    words. A snake_case token made only of Spanish function words is not an internal name."""
    q = battery.quality("Así que no hay problema de_no poder surtir por muy poco producto.", tool_results=[])
    assert q["internal_names"] == [] and "internal_names" not in q["flags"]


def test_a_field_name_with_one_spanish_looking_part_is_still_internal():
    q = battery.quality("El campo do_nothing y el on_hand de_la tienda.", tool_results=[])
    assert {"do_nothing", "on_hand"} <= set(q["internal_names"])
    assert "de_la" not in q["internal_names"]


def test_a_follow_up_traces_its_numbers_against_the_earlier_turns_of_the_conversation():
    """L13: a tool-less follow-up repeats a figure an earlier turn's tools returned; it is traceable."""
    first = {"tool_results": ['{"waste_usd": 812.4}'], "peer_texts": [], "results_complete": True}
    follow_up = {"tool_results": [], "peer_texts": [], "results_complete": True}

    sources, complete = battery.conversation_sources([first], follow_up)
    q = battery.quality("Como te dije, la merma fue de 812.40 USD.", sources, complete=complete)

    assert q["untraceable_numbers"] == [] and "untraceable_numbers" not in q["flags"]


def test_the_current_turn_alone_still_flags_a_number_no_turn_returned():
    first = {"tool_results": ['{"waste_usd": 812.4}'], "peer_texts": ["el analista dijo 30"], "results_complete": True}
    current = {"tool_results": ['{"qty": 20}'], "peer_texts": [], "results_complete": True}

    sources, complete = battery.conversation_sources([first], current)
    q = battery.quality("Pide 20, la merma fue 812.40 y el ahorro 999.", sources, complete=complete)

    assert complete is True and q["untraceable_numbers"] == ["999"]


def test_an_earlier_turn_with_incomplete_sources_makes_the_follow_up_check_incomplete():
    first = {"tool_results": [], "peer_texts": [], "results_complete": False}
    current = {"tool_results": [], "peer_texts": [], "results_complete": True}
    assert battery.conversation_sources([first], current)[1] is False


# ---- P5: first-text latency ----

def test_first_text_comes_from_the_backends_first_text_ms():
    assert battery.first_text_seconds({"status": "pending", "first_text_ms": 1534}) == 1.53
    assert battery.first_text_seconds({"status": "done"}) is None
    assert battery.first_text_seconds({"first_text_ms": "x"}) is None


def test_aggregate_and_compare_report_first_text_latency():
    turns = [{"case_id": "a", "turn_index": 0, "status": "done", "latency_s": 10.0, "first_text_s": 2.0},
             {"case_id": "b", "turn_index": 0, "status": "done", "latency_s": 12.0, "first_text_s": 4.0},
             {"case_id": "c", "turn_index": 0, "status": "done", "latency_s": 12.0, "first_text_s": None}]
    agg = battery.aggregate(turns)
    assert agg["first_text_p50_s"] == 2.0 and agg["first_text_p95_s"] == 4.0 and agg["first_text_turns"] == 2

    before = {"label": "b", "turns": [], "aggregate": battery.aggregate([])}
    after = {"label": "a", "turns": turns, "aggregate": agg}
    cmp = battery.compare(before, after)
    assert cmp["aggregate"]["first_text_p50_s"] == {"before": None, "after": 2.0, "delta": None}
    md = battery.render_markdown({"label": "a", "turns": turns, "aggregate": agg})
    assert "first text p50 2 s" in md


# ---- garbled fragments (P12) ----


@pytest.mark.parametrize(("reply", "fragment"), [
    ("Las ventas de hoyusted van bien.", "hoyusted"),
    ("Tienes que pedir en1 hora la harina.", "en1"),
    ("Hoy vendiste 1,200 piezas and la merma bajó.", "and"),
    ("La merma bajó，pero la venta perdida subió.", "，"),
    ("**Ventas**: 1,200\n**: merma 30", "**:"),
    ("Pide dela harina que falta.", "dela"),
])
def test_garbled_fragments_are_found_in_a_spanish_reply(reply, fragment):
    found = battery.garbled_fragments(reply)
    assert fragment in found
    q = battery.quality(reply, ["1200 30"], "¿cómo vamos?")
    assert "garbled" in q["flags"] and fragment in q["garbled_fragments"]


@pytest.mark.parametrize("reply", [
    "Hoy vendiste 1,200 piezas y la merma bajó a 30.",
    "**Ventas:** 1,200 piezas. **Merma:** 30 piezas.",
    "Te sugiero pedir 12 charolas para el sábado; el proveedor entrega el lunes.",
    "Revisa el SKU S030 y la sucursal Centro.",
    "Paraguas, contraseña y sobremesa son palabras normales.",
    "Porque la tienda contiene media charola de más; ellas y los demás lo saben.",
    "Pide 10 de Better For You Breakfast Sandwich y de Oatmeal W Brown Sugar And Fruit.",
])
def test_a_clean_spanish_reply_has_no_garbled_fragments(reply):
    assert battery.garbled_fragments(reply) == []
    assert "garbled" not in battery.quality(reply, ["1200 30 12"], "")["flags"]


def test_garbled_fragments_are_counted_per_turn_in_aggregates_and_compare():
    def turn(case, fragments):
        return {"case_id": case, "turn_index": 0, "status": "done", "latency_s": 1.0,
                "quality": {"flags": ["garbled"] if fragments else [], "garbled_fragments": fragments}}

    before_turns = [turn("a", ["hoyusted", "and"]), turn("b", [])]
    after_turns = [turn("a", []), turn("b", ["，"])]
    before = {"label": "shadow", "turns": before_turns, "aggregate": battery.aggregate(before_turns)}
    after = {"label": "on", "turns": after_turns, "aggregate": battery.aggregate(after_turns)}
    assert before["aggregate"]["garbled_fragments_total"] == 2
    assert before["aggregate"]["garbled_turns"] == 1
    cmp = battery.compare(before, after)
    assert cmp["aggregate"]["garbled_fragments_total"] == {"before": 2, "after": 1, "delta": -1}
    assert "garbled fragments" in battery.render_markdown(after)
    assert "garbled_fragments_total" in battery.render_compare_markdown(cmp)


# ---- garbled fragments, P13: glued possessives, and the false positives of the P12 detector ----


@pytest.mark.parametrize(("reply", "fragment"), [
    ("Revisa la alerta de merma; lasuya es la más cara.", "lasuya"),  # P12 battery, composite active_issues
    ("El proveedor entrega losuyo el lunes.", "losuyo"),
    ("Cada tienda revisa elsu inventario.", "elsu"),
    ("Vendiste con58,90 de margen.", "con58,90"),  # P12 battery: a number glued to a word
    ("Llega el21. de julio.", "el21."),
])
def test_glued_words_and_numbers_are_found(reply, fragment):
    assert fragment in battery.garbled_fragments(reply)


@pytest.mark.parametrize("reply", [
    "La decisión a8d5f01e08dc quedó pendiente de tu aprobación.",  # an id starting with a letter (P12 shadow)
    "Revisa el producto A100 y el Y2 de la línea de panadería.",  # upper-case product and line codes
    "Usa el código y2k del lote a1 para el traspaso.",  # lower-case codes after `y`/`a`
    "***Importante***: pide hoy la harina.",  # bold italic
    "Resumen del día\n\n***\n\nMerma 30 piezas.",  # a horizontal rule
    "La suya está bien; es la sucursal de su gerente y de sus clientes.",
    "Porque la tienda contiene media charola de más; ellas y los demás lo saben.",
    "Pide 10 de Better For You Breakfast Sandwich y 4 de Glazed Donut Box.",
])
def test_codes_ids_markdown_and_real_words_are_not_garbled(reply):
    assert battery.garbled_fragments(reply) == []


# ---- P13: repeated (interleaved) runs, the fast-path decision per turn, per-path medians ----


def _cases(*ids):
    return [battery.Case(i, "intent", ("q",)) for i in ids]


def test_repeat_runs_every_case_once_per_round_interleaved():
    plan = battery.schedule(_cases("a", "b"), repeat=3)
    assert [(r, c.id) for r, c in plan] == [(0, "a"), (0, "b"), (1, "a"), (1, "b"), (2, "a"), (2, "b")]
    assert [(r, c.id) for r, c in battery.schedule(_cases("a"), repeat=1)] == [(0, "a")]
    with pytest.raises(battery.BatteryError):
        battery.schedule(_cases("a"), repeat=0)


def test_decisions_from_the_audit_tag_turns_by_turn_id():
    turns = [{"turn_id": "t1"}, {"turn_id": "t2"}, {"turn_id": None}]
    tagged = battery.tag_decisions(turns, {"t1": "composite", "t2": "defer:no_intent"})
    assert [t.get("fast_path") for t in tagged] == ["composite", "defer:no_intent", None]
    assert battery.path_of(tagged[0]) == "composite"
    assert battery.path_of(tagged[1]) == "other"
    assert battery.path_of(tagged[2]) == "unknown"


def test_per_path_medians_separate_the_fast_path_from_the_unchanged_path():
    turns = [{**_turn("a", 6), "fast_path": "composite", "first_text_s": 3},
             {**_turn("a", 8), "fast_path": "composite", "first_text_s": 5},
             {**_turn("b", 20), "fast_path": "pass:complex"},
             {**_turn("c", 30)}]
    paths = battery.path_medians(turns)
    assert paths["composite"] == {"turns": 2, "latency_p50_s": 7.0, "first_text_p50_s": 4.0}
    assert paths["other"] == {"turns": 1, "latency_p50_s": 20.0, "first_text_p50_s": None}
    assert paths["unknown"]["turns"] == 1


def test_compare_pairs_repeats_and_reports_per_path_medians():
    before_turns = [{**_turn("a", 10), "repeat": 0, "fast_path": "composite"},
                    {**_turn("a", 12), "repeat": 1, "fast_path": "composite"},
                    {**_turn("b", 20), "repeat": 0, "fast_path": "defer:no_intent"}]
    after_turns = [{**_turn("a", 6), "repeat": 0, "fast_path": "composite"},
                   {**_turn("a", 8), "repeat": 1, "fast_path": "composite"},
                   {**_turn("b", 30), "repeat": 0, "fast_path": "defer:no_intent"}]
    cmp = battery.compare({"label": "shadow", "turns": before_turns, "aggregate": battery.aggregate(before_turns)},
                          {"label": "on", "turns": after_turns, "aggregate": battery.aggregate(after_turns)})
    rows = {(r["case_id"], r.get("repeat", 0)): r for r in cmp["rows"]}
    assert rows[("a", 1)]["latency_delta_s"] == -4
    assert cmp["paths"]["before"]["composite"]["latency_p50_s"] == 11.0
    assert cmp["paths"]["after"]["composite"]["latency_p50_s"] == 7.0
    assert cmp["paths"]["after"]["other"]["latency_p50_s"] == 30.0, "drift shows on the unchanged path"
    md = battery.render_compare_markdown(cmp)
    assert "## Per path (median)" in md
    assert "| composite | 2 / 2 | 11 | 7 |" in md


def test_compare_of_files_without_repeats_or_decisions_still_works():
    before = {"label": "a", "turns": [_turn("x", 10)], "aggregate": battery.aggregate([_turn("x", 10)])}
    after = {"label": "b", "turns": [_turn("x", 12)], "aggregate": battery.aggregate([_turn("x", 12)])}
    cmp = battery.compare(before, after)
    assert cmp["rows"][0]["latency_delta_s"] == 2
    assert cmp["paths"]["before"]["unknown"]["turns"] == 1


def test_the_runner_tags_a_result_file_with_audited_decisions_and_rewrites_its_summary(tmp_path):
    import run as runner

    result = tmp_path / "on-1.json"
    turns = [{**_turn("a", 6), "turn_id": "t1"}, {**_turn("b", 20), "turn_id": "t2"}]
    result.write_text(json.dumps({"label": "on", "started_at": "x", "store_id": "S001", "sim_today": "d",
                                  "turns": turns, "aggregate": battery.aggregate(turns)}), encoding="utf-8")
    decisions = tmp_path / "decisions.json"
    decisions.write_text(json.dumps([{"turn_id": "t1", "fast_path": "composite"},
                                     {"turn_id": "t2", "fast_path": "pass:complex"}]), encoding="utf-8")
    runner.main(["tag", str(result), str(decisions)])
    tagged = json.loads(result.read_text(encoding="utf-8"))
    assert [t["fast_path"] for t in tagged["turns"]] == ["composite", "pass:complex"]
    assert tagged["aggregate"]["paths"]["composite"]["turns"] == 1
    assert result.with_suffix(".md").exists()


def test_the_runner_accepts_a_repeat_count():
    import run as runner

    args = runner.parser().parse_args(["run", "--label", "x", "--repeat", "3"])
    assert args.repeat == 3
    assert runner.parser().parse_args(["run", "--label", "x"]).repeat == 1
