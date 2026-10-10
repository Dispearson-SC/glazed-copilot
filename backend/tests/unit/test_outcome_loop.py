"""R2: advancing the clock closes the loop: approved decisions get a measured outcome, persisted and visible everywhere."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from glazed_backend.adapters.driven.memory import InMemoryExperienceMemory
from glazed_backend.adapters.driving.app import Container, create_app
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)
from tests.unit.test_sentinel_api import ISSUE, ISSUE_X

DAY0 = date(2026, 3, 11)


class Metrics(FakeMetrics):
    """Outcome of a decision made on DAY0: only days after it and up to as_of are measurable (3-day horizon)."""

    def observed_outcome(self, store_id, as_of, action_type, params, partial=False):
        self.calls.append(("observed_outcome", as_of, partial))
        d0 = date.fromisoformat(params["decision_as_of"])
        days = min((as_of - d0).days, 3)
        if days < (1 if partial else 3):
            return None
        end = d0 + timedelta(days=days)
        return {"net_usd": 18.0, "window": [(d0 + timedelta(days=1)).isoformat(), end.isoformat()], "waste_usd": 2.5,
                "lost_sales_usd": 1.25, "censored": True, "units_sold": 9 * days, "units_forecast": 10.0 * days}


@pytest.fixture
def env():
    metrics = Metrics({DAY0: [ISSUE_X], DAY0 + timedelta(days=1): [ISSUE_X]})
    c = Container(metrics=metrics, core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(),
                  proposals=InMemoryProposals(), executions=InMemoryExecutions(), backtests=InMemoryBacktests(),
                  trace=InMemoryTrace(), clock=FakeClock(), memory=InMemoryExperienceMemory())
    return TestClient(create_app(c)), c


def approved(client, sim=DAY0.isoformat(), approve=True):
    case = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": sim}).json()
    h = {"X-Glazed-Case": case["case_id"]}
    client.get("/internal/v1/issues", headers=h)
    pid = client.post("/internal/v1/proposals", headers=h, json={"issue_id": ISSUE["issue_id"], "option_id": "opt-place"}).json()["proposal_id"]
    client.post(f"/api/v1/proposals/{pid}/decision", json={"approved": approve, "reason": "" if approve else "no"})
    return case["case_id"], pid


def advance(client, cid, days):
    r = client.post(f"/api/v1/cases/{cid}/advance", json={"days": days})
    assert r.status_code == 200, r.text
    return r.json()


def test_one_day_after_the_decision_a_partial_outcome_is_returned_without_verdict(env):
    client, c = env
    cid, pid = approved(client)
    out = advance(client, cid, 1)["outcomes"]
    assert [(o["decision_id"], o["complete"], o["verdict"]) for o in out] == [(pid, False, None)]
    assert out[0]["window_days"] == 1 and out[0]["observed"]["waste_usd"] == 2.5
    row = next(r for r in client.get(f"/api/v1/cases/{cid}/decisions").json() if r["kind"] == "outcome")
    assert row["status"] == "measuring" and row["outcome"]["complete"] is False
    assert c.outcomes.get(pid).complete is False
    assert [m for m in client.get(f"/api/v1/cases/{cid}/memories").json() if m["source"] == "outcome"] == []  # not final


def test_no_outcome_on_the_day_of_the_decision_or_for_rejected_decisions(env):
    client, _ = env
    cid, _ = approved(client)
    assert advance(client, cid, 0)["outcomes"] == []
    rid, _ = approved(client, approve=False)
    assert advance(client, rid, 4)["outcomes"] == []


def test_past_the_horizon_the_outcome_is_final_persisted_and_returned_once(env):
    client, c = env
    cid, pid = approved(client)
    advance(client, cid, 1)
    (o,) = advance(client, cid, 3)["outcomes"]
    assert o["complete"] is True and o["verdict"] == "dentro de lo esperado" and o["measured_as_of"] == "2026-03-15"
    assert o["observed"]["waste_usd"] == 2.5 and o["observed"]["lost_sales_usd"] == 1.25 and o["observed"]["censored"] is True
    assert o["sold_vs_forecast"] == {"units_sold": 27, "units_forecast": 30.0, "delta_units": -3.0, "delta_pct": -10.0}
    stored = c.outcomes.get(pid)
    assert stored.complete and stored.payload["verdict_code"] == "within"
    assert advance(client, cid, 1)["outcomes"] == []  # final: never measured again


def test_final_outcome_is_an_outcome_row_in_decisions_a_verified_memory_and_part_of_the_history(env):
    client, c = env
    cid, pid = approved(client)
    advance(client, cid, 4)
    rows = client.get(f"/api/v1/cases/{cid}/decisions").json()
    out = next(r for r in rows if r["kind"] == "outcome")
    assert out["status"] == "measured" and out["as_of"] == "2026-03-14" and out["outcome"]["verdict"] == "dentro de lo esperado"
    assert rows[-1]["kind"] == "outcome"
    mem = [m for m in client.get(f"/api/v1/cases/{cid}/memories").json() if m["source"] == "outcome"]
    assert len(mem) == 1 and mem[0]["verified"] is True and mem[0]["text"].startswith("Resultado medido")
    assert mem[0]["created_at"].startswith("2026-03-15")  # the simulated day it became known, not the wall clock
    log = client.get("/internal/v1/history", headers={"X-Glazed-Case": cid}).json()["decision_log"]
    o = log[0]["outcome"]
    assert o["verdict"] == "dentro de lo esperado" and o["waste_usd"] == 2.5 and o["lost_sales_usd"] == 1.25
    assert o["sold_vs_forecast"]["units_forecast"] == 30.0 and o["censored"] is True and o["complete"] is True
    assert [e.decision_id for e in c.memory.recall("S030", "", 10) if e.kind == "outcome"] == [pid]  # agents recall it too
    assert len([m for m in client.get(f"/api/v1/cases/{cid}/memories").json() if m["source"] == "backboard"]) == 0  # no duplicate


def test_nothing_after_the_case_date_is_ever_read(env):
    client, c = env
    cid, _ = approved(client)
    advance(client, cid, 2)
    advance(client, cid, 2)
    case_dates = {date(2026, 3, 11) + timedelta(days=n) for n in range(0, 5)}
    assert all(call[1] in case_dates for call in c.metrics.calls if call[0] == "observed_outcome")
    assert max(call[1] for call in c.metrics.calls if call[0] == "observed_outcome") == date(2026, 3, 15)


def test_an_earlier_dated_case_does_not_see_an_outcome_measured_later(env):
    client, c = env
    cid, pid = approved(client)
    early = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": DAY0.isoformat()}).json()["case_id"]
    advance(client, cid, 4)
    mine = [m for m in client.get(f"/api/v1/cases/{early}/memories").json() if m["source"] == "outcome"]
    assert mine == []
    log = client.get("/internal/v1/history", headers={"X-Glazed-Case": early}).json()["decision_log"]
    assert all(d["outcome"] is None for d in log)


def test_archived_cases_outcomes_stay_out_of_other_cases(env):
    client, _ = env
    cid, _ = approved(client)
    other = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": DAY0.isoformat()}).json()["case_id"]
    advance(client, cid, 4)
    advance(client, other, 4)
    assert any(m["source"] == "outcome" for m in client.get(f"/api/v1/cases/{other}/memories").json())
    client.post(f"/api/v1/cases/{cid}/archive")
    assert [m for m in client.get(f"/api/v1/cases/{other}/memories").json() if m["source"] == "outcome"] == []
