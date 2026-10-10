import asyncio
import os
from datetime import date
from types import SimpleNamespace

import pytest

from glazed_backend.adapters.driven.backboard_memory import BackboardMemory
from glazed_backend.adapters.driven.memory import InMemoryAssistants, InMemoryExperienceMemory
from glazed_backend.application import (AdvanceSimClock, DecideProposal, RecallExperiences, RecordOutcome,
                                        StartCase, SubmitProposal)
from glazed_backend.application.seed import parse_promo_baseline
from glazed_backend.domain import Experience
from glazed_backend.domain.models import MemoryUnavailable
from tests.fakes import (FakeMetrics, InMemoryAlerts, InMemoryCases, InMemoryExecutions, InMemoryProposals)

ISSUE = {"issue_id": "S030|overstock_waste|SKU-9", "kind": "overstock_waste", "severity_usd": 50.0, "sku": "SKU-9"}


@pytest.fixture
def w():
    class W: ...
    w = W()
    w.cases, w.alerts, w.props, w.execs = InMemoryCases(), InMemoryAlerts(), InMemoryProposals(), InMemoryExecutions()
    w.mem = InMemoryExperienceMemory()
    w.case = StartCase(w.cases).execute("S030", date(2026, 3, 10))
    w.prop = SubmitProposal(w.cases, w.props).execute(w.case.case_id, ISSUE["issue_id"], "place_order",
                                                      {"sku": "SKU-9", "qty": 2}, "N2", "r")
    return w


def decide(w, approved, reason):
    return DecideProposal(w.cases, w.props, w.execs, w.alerts, w.mem).execute(w.prop.proposal_id, approved, reason)


def test_decide_writes_compact_experience_with_decision_id(w):
    decide(w, False, "too expensive")
    (exp,) = w.mem.recall("S030", "overstock", 5)
    assert exp.text.startswith("[S030 · overstock_waste · SKU-9 · 2026-03-10] place_order REJECTED. too expensive.")
    assert exp.text.endswith(f"decision_id={w.prop.proposal_id}") and exp.decision_id == w.prop.proposal_id
    assert exp.kind == "decision"


def test_decide_approved_includes_simulated_option(w):
    decide(w, True, "ok")
    (exp,) = w.mem.recall("S030", "place_order", 5)
    assert "APPROVED" in exp.text and '"qty": 2' in exp.text


def test_memory_failure_never_breaks_decision(w):
    class Boom:
        def remember(self, *a): raise MemoryUnavailable("down")
        def recall(self, *a): raise MemoryUnavailable("down")
    ex = DecideProposal(w.cases, w.props, w.execs, w.alerts, Boom()).execute(w.prop.proposal_id, True, "")
    assert ex.status == "executed"


def test_record_outcome_writes_measured_result(w):
    decide(w, True, "ok")
    RecordOutcome(w.props, w.cases, w.mem).execute(w.prop.proposal_id, "waste fell from $40 to $12 (measured)")
    kinds = {e.kind for e in w.mem.recall("S030", "waste", 5)}
    assert "outcome" in kinds


def test_recall_degrades_with_warning(w):
    class Down:
        def recall(self, *a): raise MemoryUnavailable("BACKBOARD_API_KEY missing")
    res = RecallExperiences(Down()).execute("S030", "q", 5)
    assert res == ([], "BACKBOARD_API_KEY missing")
    assert RecallExperiences(None).execute("S030", "q", 5)[0] == []


def test_in_memory_memory_is_isolated_per_store(w):
    w.mem.remember("S001", Experience("promo uplift low", "promo_evaluation", "S001"))
    assert w.mem.recall("S030", "promo", 5) == []


# --- Backboard adapter with a fake async client ---------------------------------------------------
class FakeBB:
    def __init__(self, fail_times=0):
        self.assistants, self.added, self.searched, self.fail = 0, [], [], fail_times

    async def create_assistant(self, name, **kw):
        self.assistants += 1
        return SimpleNamespace(assistant_id=f"a-{name}")

    async def add_memory(self, assistant_id, content, metadata=None):
        self.added.append((assistant_id, content, metadata))
        return {"memory_id": "m1"}

    async def search_memories(self, assistant_id, query, limit=5):
        if self.fail:
            self.fail -= 1
            from backboard.exceptions import BackboardRateLimitError
            raise BackboardRateLimitError("slow down", 429, None)
        self.searched.append((assistant_id, query, limit))
        return {"memories": [{"id": "m1", "content": "[S030 · x] hello decision_id=d1", "score": 0.9,
                              "metadata": {"decision_id": "d1", "kind": "decision"},
                              "created_at": "2026-03-10T00:00:00+00:00"}], "total_count": 1}


def bb(client, key="k", **kw):
    return BackboardMemory(key, InMemoryAssistants(), client_factory=lambda: client, sleep=lambda s: None, **kw)


def test_one_assistant_per_store_created_lazily_and_persisted():
    c, repo = FakeBB(), InMemoryAssistants()
    m = BackboardMemory("k", repo, client_factory=lambda: c, sleep=lambda s: None)
    assert c.assistants == 0
    m.remember("S030", Experience("t1", "decision", "S030", "d1"))
    m.remember("S030", Experience("t2", "decision", "S030", "d2"))
    m.recall("S030", "q", 3)
    m.remember("S001", Experience("t3", "decision", "S001"))
    assert c.assistants == 2 and repo.get("S030") == "a-Glazed · S030"
    assert c.added[0][2]["decision_id"] == "d1" and c.searched[0][2] == 3


def test_recall_maps_results_and_uses_explicit_memory_calls_only():
    (e,) = bb(FakeBB()).recall("S030", "q", 5)
    assert (e.text, e.decision_id, e.kind, e.score) == ("[S030 · x] hello decision_id=d1", "d1", "decision", 0.9)


def test_missing_key_raises_unavailable():
    with pytest.raises(MemoryUnavailable, match="BACKBOARD_API_KEY"):
        bb(FakeBB(), key="").recall("S030", "q", 5)


def test_rate_limit_is_retried_with_backoff_then_succeeds():
    sleeps = []
    c = FakeBB(fail_times=2)
    m = BackboardMemory("k", InMemoryAssistants(), client_factory=lambda: c, sleep=sleeps.append)
    assert len(m.recall("S030", "q", 5)) == 1 and sleeps == [0.5, 1.0]


def test_persistent_rate_limit_becomes_unavailable():
    with pytest.raises(MemoryUnavailable, match="429|rate"):
        bb(FakeBB(fail_times=99)).recall("S030", "q", 5)


def test_unexpected_error_becomes_unavailable():
    class Bad(FakeBB):
        async def create_assistant(self, name, **kw): raise RuntimeError("boom")
    with pytest.raises(MemoryUnavailable):
        bb(Bad()).remember("S030", Experience("t", "decision", "S030"))


@pytest.mark.skipif(not os.environ.get("BACKBOARD_API_KEY"), reason="BACKBOARD_API_KEY not set")
def test_live_backboard_roundtrip():
    m = BackboardMemory(os.environ["BACKBOARD_API_KEY"], InMemoryAssistants())
    m.remember("S999", Experience("[S999 · test] live roundtrip decision_id=live1", "decision", "S999", "live1"))
    m.recall("S999", "live roundtrip", 3)


# --- seed parsing ----------------------------------------------------------------------------------
MD = """## 3. Promociones
| Promo | Tipo / % | Esperado | Uplift real (±28d) | Costo desc. | Efecto margen neto [S] |
|---|---|---|---|---|---|
| PR002 Bakery Dozen | Bundle 15 | 30 | **-11** (-8) | $55.4 k | **-$103 k** |
| PR013 Mystery | sin ejecutar | 20 | +14 (+6.5) sin descuento | $2.3 k lealtad | placebo |
## 4. Inventario
| X | y |
"""


def test_parse_promo_baseline_reads_only_section_3_rows():
    exps = parse_promo_baseline(MD)
    assert [e.kind for e in exps] == ["promo_evaluation"] * 2
    assert "PR002 Bakery Dozen" in exps[0].text and "-11" in exps[0].text and "-$103 k" in exps[0].text
    assert "baseline" in exps[0].text and exps[0].decision_id is None


def test_parse_real_baseline_has_13_rows():
    p = os.path.join(os.path.dirname(__file__), "../../../data/docs/analisis_estado.md")
    if not os.path.exists(p):
        pytest.skip("baseline not available")
    assert len(parse_promo_baseline(open(p, encoding="utf-8").read())) == 13


def test_assistant_is_named_after_the_store_display_name_and_renamed_when_known():
    c, repo = FakeBB(), InMemoryAssistants()
    c.renamed = []

    async def update_assistant(assistant_id, name=None, **kw):
        c.renamed.append((assistant_id, name))
    c.update_assistant = update_assistant
    m = BackboardMemory("k", repo, client_factory=lambda: c, sleep=lambda s: None,
                        display_name=lambda sid: "Bayfront Municipal Airport · Gate Area West")
    m.remember("S030", Experience("t1", "decision", "S030"))
    assert repo.get("S030") == "a-Glazed · Bayfront Municipal Airport · Gate Area West"
    repo.set("S001", "old-id")
    assert m.rename("S001") == "Glazed · Bayfront Municipal Airport · Gate Area West"
    assert c.renamed == [("old-id", "Glazed · Bayfront Municipal Airport · Gate Area West")]
    assert m.rename("S777") is None  # no assistant yet: nothing to rename


def test_seeded_promo_experiences_carry_the_promo_id_as_ref_in_text_and_field():
    exps = parse_promo_baseline(MD)
    assert exps[0].ref == "PR002" and exps[0].text.endswith("ref=PR002") and exps[0].decision_id is None


def test_ref_roundtrips_through_backboard_metadata():
    c = FakeBB()
    m = bb(c)
    m.remember("S030", Experience("t", "promo_evaluation", "S030", None, ref="PR009"))
    assert c.added[0][2]["ref"] == "PR009" and "decision_id" not in c.added[0][2]

    class WithRef(FakeBB):
        async def search_memories(self, assistant_id, query, limit=5):
            return {"memories": [{"content": "x", "metadata": {"kind": "promo_evaluation", "ref": "PR009"}}]}
    assert bb(WithRef()).recall("S030", "q")[0].ref == "PR009"
