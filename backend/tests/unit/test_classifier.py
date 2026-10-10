import json
import os
from types import SimpleNamespace

import httpx
import pytest

from glazed_backend.adapters.driven.classifiers import (BackboardSystemOne, ChainClassifier, KeywordClassifier,
                                                        LLMFallback)
from glazed_backend.ports.classifier import ClassifierError, DEVIATION_CAUSE, REJECTION_REASON, escape_label, labels_for


def test_label_sets_always_include_the_escape_label():
    assert REJECTION_REASON == ("precio", "imagen_de_marca", "falta_personal", "desconfia_del_dato", "mal_momento",
                                "prefiere_no_quedarse_corto", "otro", "needs_review")
    assert DEVIATION_CAUSE == ("bloqueo", "clima", "evento_local", "falla_proveedor", "error_operativo", "no_match")
    assert escape_label("rejection_reason") == "needs_review" and escape_label("deviation_cause") == "no_match"
    with pytest.raises(ClassifierError):
        labels_for("mood")


def test_keyword_fake_is_deterministic_and_never_invents_a_label():
    k = KeywordClassifier()
    assert k.classify("rejection_reason", "Es demasiado caro, el precio no me convence").label == "precio"
    assert k.classify("deviation_cause", "hubo un bloqueo en la carretera").label == "bloqueo"
    r = k.classify("rejection_reason", "asdf qwer")
    assert r.label == "needs_review" and r.calibrated is False and r.model == "keyword-fake"


# --- Backboard System One ---------------------------------------------------------------------------------------------
class FakeBB:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    async def create_assistant(self, **kw):
        return SimpleNamespace(assistant_id="a1")

    async def create_thread(self, assistant_id):
        return SimpleNamespace(thread_id="t1")

    async def add_message(self, thread_id, **kw):
        self.calls.append((thread_id, kw))
        so = SimpleNamespace(model="jev-1.13.0", answers={"label": self.answer}, usage={})
        return SimpleNamespace(system_one=so)


def jev(answer, **kw):
    c = FakeBB(answer)
    return BackboardSystemOne("key", client_factory=lambda: c, **kw), c


def test_backboard_adapter_asks_a_typesafe_choice_question_with_every_label():
    adapter, c = jev({"choice": "precio", "probabilities": {"precio": 0.81, "otro": 0.1}})
    r = adapter.classify("rejection_reason", "muy caro")
    assert (r.label, r.confidence, r.model, r.calibrated, r.adapter) == ("precio", 0.81, "jev-1.13.0", True, "backboard_system_one")
    thread, kw = c.calls[0]
    assert thread == "t1" and kw["llm_provider"] == "typesafe" and kw["model_name"] == "jev-1.13.0" and kw["stream"] is False
    q = kw["system_one"]["questions"]["label"]
    assert q["type"] == "choice" and set(q["criteria"]) == set(REJECTION_REASON) and kw["content"] == "muy caro"


def test_backboard_adapter_reads_other_answer_shapes_and_clamps_to_the_label_set():
    adapter, _ = jev({"probabilities": {"mal_momento": 0.55, "precio": 0.3}})
    assert adapter.classify("rejection_reason", "x").label == "mal_momento"
    adapter, _ = jev({"choice": "inventado", "probabilities": {"inventado": 0.9}})
    assert adapter.classify("rejection_reason", "x").label == "needs_review"


def test_low_confidence_falls_to_the_escape_label():
    adapter, _ = jev({"choice": "precio", "probabilities": {"precio": 0.2}})
    r = adapter.classify("rejection_reason", "x")
    assert r.label == "needs_review" and r.confidence == 0.2


def test_backboard_adapter_without_key_or_with_unusable_answer_raises():
    with pytest.raises(ClassifierError, match="BACKBOARD_API_KEY"):
        BackboardSystemOne("", client_factory=lambda: None).classify("rejection_reason", "x")
    adapter, _ = jev({"unexpected": 1})
    with pytest.raises(ClassifierError):
        adapter.classify("rejection_reason", "x")


# --- LLM fallback -----------------------------------------------------------------------------------------------------
def llm(content, status=200, calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})
    return LLMFallback("secret-key", transport=httpx.MockTransport(handler))


def test_llm_fallback_returns_strict_json_labels_marked_uncalibrated():
    calls = []
    r = llm('{"label": "falta_personal", "confidence": 0.7}', calls=calls).classify("rejection_reason", "no tengo gente")
    assert (r.label, r.confidence, r.calibrated, r.adapter) == ("falta_personal", 0.7, False, "llm_fallback")
    sent = json.loads(calls[0].content)
    assert calls[0].headers["authorization"] == "Bearer secret-key" and sent["messages"][-1]["content"] == "no tengo gente"
    assert all(label in sent["messages"][0]["content"] for label in REJECTION_REASON)


def test_llm_fallback_tolerates_think_blocks_and_fences_and_clamps_unknown_labels():
    r = llm('<think>hmm</think>```json\n{"label": "precio", "confidence": 0.9}\n```').classify("rejection_reason", "x")
    assert r.label == "precio"
    assert llm('{"label": "otra_cosa", "confidence": 0.9}').classify("deviation_cause", "x").label == "no_match"


def test_llm_fallback_errors_do_not_leak_the_key():
    with pytest.raises(ClassifierError) as e:
        llm("not json").classify("rejection_reason", "x")
    assert "secret-key" not in str(e.value)
    with pytest.raises(ClassifierError) as e:
        llm("{}", status=401).classify("rejection_reason", "x")
    assert "secret-key" not in str(e.value) and "401" in str(e.value)
    with pytest.raises(ClassifierError, match="MINIMAX_API_KEY"):
        LLMFallback("").classify("rejection_reason", "x")


# --- chain ------------------------------------------------------------------------------------------------------------
class Boom:
    def classify(self, kind, text):
        raise ClassifierError("down")


def test_chain_tries_adapters_in_order_and_reports_the_one_that_answered():
    r = ChainClassifier([Boom(), KeywordClassifier()]).classify("rejection_reason", "el precio es alto")
    assert r.label == "precio" and r.adapter == "keyword_fake" and "down" in r.warning


def test_chain_with_everything_down_answers_with_the_escape_label():
    r = ChainClassifier([Boom()]).classify("deviation_cause", "x")
    assert r.label == "no_match" and r.confidence == 0.0 and r.model == "none" and r.calibrated is False
    r = ChainClassifier([]).classify("rejection_reason", "x")
    assert r.label == "needs_review"


# --- live (skipped without keys) --------------------------------------------------------------------------------------
@pytest.mark.skipif(not os.environ.get("BACKBOARD_API_KEY"), reason="no BACKBOARD_API_KEY")
def test_live_backboard_system_one():
    r = BackboardSystemOne(os.environ["BACKBOARD_API_KEY"]).classify("rejection_reason", "es demasiado caro para mi tienda")
    assert r.label in REJECTION_REASON and r.model.startswith("jev")


@pytest.mark.skipif(not os.environ.get("MINIMAX_API_KEY"), reason="no MINIMAX_API_KEY")
def test_live_minimax_fallback():
    r = LLMFallback(os.environ["MINIMAX_API_KEY"]).classify("rejection_reason", "es demasiado caro para mi tienda")
    assert r.label in REJECTION_REASON and r.calibrated is False


# --- wiring -----------------------------------------------------------------------------------------------------------
from datetime import date  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from glazed_backend.adapters.driven.memory import InMemoryExperienceMemory  # noqa: E402
from glazed_backend.adapters.driving.app import Container, create_app  # noqa: E402
from glazed_backend.application import DecideProposal, StartCase, SubmitProposal  # noqa: E402
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,  # noqa: E402
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)


def test_internal_classify_endpoint_returns_label_confidence_model_calibrated():
    c = Container(metrics=FakeMetrics(), core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(),
                  proposals=InMemoryProposals(), executions=InMemoryExecutions(), backtests=InMemoryBacktests(),
                  trace=InMemoryTrace(), clock=FakeClock(), classifier=KeywordClassifier())
    client = TestClient(create_app(c))
    r = client.post("/internal/v1/classify", json={"kind": "rejection_reason", "text": "es muy caro"})
    assert r.status_code == 200 and r.json() == {"label": "precio", "confidence": 0.9, "model": "keyword-fake",
                                                 "calibrated": False, "adapter": "keyword_fake"}
    assert client.post("/internal/v1/classify", json={"kind": "mood", "text": "x"}).status_code == 400
    assert client.post("/internal/v1/classify", json={"kind": "deviation_cause", "text": "  "}).status_code == 400
    c.classifier = None  # nothing configured: still an answer, the escape label
    assert client.post("/internal/v1/classify", json={"kind": "deviation_cause", "text": "x"}).json()["label"] == "no_match"


@pytest.fixture
def w():
    class W: ...
    w = W()
    w.cases, w.alerts, w.props, w.execs = InMemoryCases(), InMemoryAlerts(), InMemoryProposals(), InMemoryExecutions()
    w.mem = InMemoryExperienceMemory()
    w.case = StartCase(w.cases).execute("S030", date(2026, 3, 10))
    w.prop = SubmitProposal(w.cases, w.props).execute(w.case.case_id, "S030|overstock_waste|SKU-9", "place_order",
                                                      {"sku": "SKU-9"}, "N2", "r")
    return w


def decide(w, approved, reason, classifier):
    return DecideProposal(w.cases, w.props, w.execs, w.alerts, w.mem, classifier).execute(w.prop.proposal_id, approved, reason)


def test_rejection_is_classified_and_stored_on_the_proposal_and_in_the_memory_text(w):
    decide(w, False, "me parece muy caro", KeywordClassifier())
    p = w.props.get(w.prop.proposal_id)
    assert (p.reason_category, p.reason_confidence) == ("precio", 0.9)
    (exp,) = w.mem.recall("S030", "overstock", 5)
    assert "Reason category: precio (confidence 0.90)." in exp.text and exp.text.endswith(f"decision_id={w.prop.proposal_id}")


def test_approval_is_not_classified_and_classifier_failures_never_block_a_decision(w):
    class Spy:
        calls = 0

        def classify(self, kind, text):
            Spy.calls += 1
            raise RuntimeError("boom")
    decide(w, True, "ok", Spy())
    assert Spy.calls == 0 and w.props.get(w.prop.proposal_id).reason_category is None
    w2 = w.__class__()
    w2.cases, w2.alerts, w2.props, w2.execs, w2.mem = InMemoryCases(), InMemoryAlerts(), InMemoryProposals(), InMemoryExecutions(), InMemoryExperienceMemory()
    case = StartCase(w2.cases).execute("S030", date(2026, 3, 10))
    w2.prop = SubmitProposal(w2.cases, w2.props).execute(case.case_id, "S030|x|y", "place_order", {}, "N2", "r")
    decide(w2, False, "no", Spy())
    p = w2.props.get(w2.prop.proposal_id)
    assert Spy.calls == 1 and p.status == "rejected" and p.reason_category is None
