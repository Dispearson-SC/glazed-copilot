"""P14 battery fixes (scripts/stress/battery.py): the glued-digit detector at a sentence start and the
fast-path buckets that separate the true control (`defer:*`) from the turns a pass changes (`pass:*`).
No network, no backend. Run: `pytest scripts/stress/test_battery_p14.py`."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import battery  # noqa: E402


# ---- glued digits: case (P13 review warning, battery.py:156) ----

@pytest.mark.parametrize(("reply", "fragment"), [
    ("En14 tiendas la merma bajó.", "En14"),  # a sentence starts with the glued word
    ("Del5 al 10 de julio llega harina.", "Del5"),
    ("Hoy vendiste. Con58,90 de margen.", "Con58,90"),
    ("Pide el10 de julio.", "el10"),  # lower case still found
])
def test_a_number_glued_to_a_capitalised_word_is_found(reply, fragment):
    assert fragment in battery.garbled_fragments(reply)


@pytest.mark.parametrize("reply", [
    "Revisa el producto A100 y el Y2 de la línea de panadería.",
    "La norma EN14 aplica al empaque.",  # an all-capital code
    "El lote AL5 llega el lunes.",
])
def test_codes_in_capitals_are_not_glued_digits(reply):
    assert battery.garbled_fragments(reply) == []


# ---- buckets: defer (true control) apart from pass:* (P13 review warning, battery.py:332-337) ----

def _turn(case, latency, verdict=None, first=None):
    t = {"case_id": case, "turn_index": 0, "status": "done", "latency_s": latency, "first_text_s": first,
         "tool_calls": 1, "peer_asks": 0, "quality": {"flags": []}}
    if verdict:
        t["fast_path"] = verdict
    return t


def test_each_verdict_falls_in_its_bucket():
    assert battery.bucket_of(_turn("a", 1, "composite")) == "composite"
    assert battery.bucket_of(_turn("a", 1, "defer:no_intent")) == "defer"
    assert battery.bucket_of(_turn("a", 1, "defer:route_covers")) == "defer"
    assert battery.bucket_of(_turn("a", 1, "pass:uncovered")) == "pass"
    assert battery.bucket_of(_turn("a", 1, "pass:complex")) == "pass"
    assert battery.bucket_of(_turn("a", 1)) == "unknown"


def test_path_medians_report_defer_and_pass_separately():
    turns = [_turn("a", 6, "composite"), _turn("b", 8, "defer:no_intent"), _turn("c", 10, "defer:no_intent"),
             _turn("d", 30, "pass:uncovered", first=12)]
    paths = battery.path_medians(turns)
    assert paths["defer"] == {"turns": 2, "latency_p50_s": 9.0, "first_text_p50_s": None}
    assert paths["pass"] == {"turns": 1, "latency_p50_s": 30.0, "first_text_p50_s": 12.0}
    assert paths["composite"]["turns"] == 1


def test_compare_markdown_shows_defer_as_the_control_and_pass_apart():
    before = [_turn("a", 6, "composite"), _turn("b", 8, "defer:no_intent"), _turn("d", 5, "pass:uncovered")]
    after = [_turn("a", 6, "composite"), _turn("b", 11, "defer:no_intent"), _turn("d", 30, "pass:uncovered")]
    cmp = battery.compare({"label": "shadow", "turns": before, "aggregate": battery.aggregate(before)},
                          {"label": "on", "turns": after, "aggregate": battery.aggregate(after)})
    assert cmp["paths"]["after"]["defer"]["latency_p50_s"] == 11.0
    assert cmp["paths"]["after"]["pass"]["latency_p50_s"] == 30.0
    md = battery.render_compare_markdown(cmp)
    assert "| defer (true control) | 1 / 1 | 8 | 11 |" in md
    assert "| pass | 1 / 1 | 5 | 30 |" in md
    assert "| other |" not in md, "the mixed bucket hid a behaviour change inside the drift control"
