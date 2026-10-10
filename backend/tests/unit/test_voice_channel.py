"""Push-to-talk: the voice flag tags only the Core-bound text; the tag never reaches history or replies."""
from datetime import date

from glazed_backend.adapters.driven.memory import InMemoryTurns
from glazed_backend.application import VOICE_TAG, AskAgent, GetTurn, ListTurns, StartCase, TurnTracker
from glazed_backend.application.reply_sanitizer import clean_reply, sanitize_reply
from tests.fakes import FakeClock, FakeCore, InMemoryCases


def _env():
    cases, core, clock, turns = InMemoryCases(), FakeCore(), FakeClock(), InMemoryTurns()
    ask = AskAgent(cases, core, TurnTracker(), clock, turns)
    case = StartCase(cases).execute(store_id="S030", sim_today=date(2026, 3, 10))
    return cases, core, clock, turns, ask, case


def test_voice_adds_the_tag_only_to_the_text_sent_to_the_core():
    cases, core, clock, turns, ask, case = _env()
    tid = ask.execute(case.case_id, "que hago con los roles", voice=True)
    assert VOICE_TAG == "[canal: voz] "
    assert core.sent[0][2] == "[canal: voz] que hago con los roles"
    assert turns.get(tid).user_text == "que hago con los roles"


def test_history_shows_the_clean_text():
    cases, core, clock, turns, ask, case = _env()
    tid = ask.execute(case.case_id, "hola equipo", voice=True)
    core.turns[tid] = {"turn_id": tid, "status": "finished", "text": "Listo."}
    get = GetTurn(cases, core, TurnTracker(), clock, turns=turns)
    items = ListTurns(cases, core, turns, get, TurnTracker()).execute(case.case_id)
    assert items[0]["user_text"] == "hola equipo"


def test_default_is_text_and_unchanged():
    cases, core, clock, turns, ask, case = _env()
    ask.execute(case.case_id, "hola")
    assert core.sent[0][2] == "hola"


def test_sanitizer_strips_a_leaked_voice_tag():
    assert sanitize_reply("[canal: voz] Pide tres cajas.")[0] == "Pide tres cajas."
    assert "canal" not in clean_reply("Pide [Canal : VOZ] tres cajas.").text
    assert sanitize_reply("Pide tres cajas.")[0] == "Pide tres cajas."
