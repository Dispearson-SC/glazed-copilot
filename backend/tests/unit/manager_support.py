"""Shared builder for the Wave 12 manager-metric route tests (public and internal)."""
from datetime import date, timedelta

from fastapi.testclient import TestClient

from glazed_backend.adapters.driven.forecast import BaselineForecast, WeekdayFlow
from glazed_backend.adapters.driving.app import Container, create_app
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)

AS_OF = date(2026, 7, 19)  # a Sunday
START = date(2026, 3, 1)


def prod(name, dept="Bakery", cost=1.0, price=3.0, life=None, supplier="SUP01"):
    return {"product_name": name, "department": dept, "unit_cost": cost, "price": price, "shelf_life_days": life,
            "supplier_id": supplier}


def build(configure=None, as_of=AS_OF):
    m = FakeMetrics()
    if configure:
        configure(m)
    c = Container(metrics=m, core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(), proposals=InMemoryProposals(),
                  executions=InMemoryExecutions(), backtests=InMemoryBacktests(), trace=InMemoryTrace(), clock=FakeClock(),
                  forecasters=[BaselineForecast()], flow_forecaster=WeekdayFlow())
    client = TestClient(create_app(c))
    cid = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": as_of.isoformat()}).json()["case_id"]
    return client, cid, m


def dates_after(payload, as_of=AS_OF, path=""):
    """Every ISO date string in `payload` later than as_of, with its path (to assert nothing is unflagged)."""
    found = []
    if isinstance(payload, dict):
        for k, v in payload.items():
            found += dates_after(v, as_of, f"{path}.{k}")
    elif isinstance(payload, list):
        for i, v in enumerate(payload):
            found += dates_after(v, as_of, f"{path}[{i}]")
    elif isinstance(payload, str) and len(payload) == 10 and payload[4] == "-" and payload[7] == "-":
        try:
            if date.fromisoformat(payload) > as_of:
                found.append(path)
        except ValueError:
            pass
    return found
