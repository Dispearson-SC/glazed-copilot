import time
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from glazed_backend.adapters.driving.app import Container, create_app
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)

AS_OF = date(2026, 3, 10)


def op_issue(n: int, sev: float, kind: str = "overstock_waste") -> dict:
    return {"issue_id": f"S030|{kind}|SKU-{n}", "kind": kind, "sku": f"SKU-{n}", "product_name": f"Producto {n}",
            "category": "operational", "severity_usd": sev, "store_id": "S030", "as_of": str(AS_OF),
            "as_of_date": str(AS_OF), "engine_version": "v1", "store_display_name": "x",
            "evidence": [{"metric": f"m{i}", "value": i, "unit": "USD", "source": "inventory_daily"} for i in range(6)],
            "data_caveats": [],
            "options": [{"option_id": f"o{n}a", "action_type": "skip_order", "net_usd_mid": sev / 2,
                         "confidence": {"score": 0.8, "n_backtest": 600, "method": "backtest_replay",
                                        "effect_mean_usd": 9.9, "noise_floor_usd": 1.0, "noise_capped": False},
                         "tier": "N2", "tier_reasons": ["x" * 80]},
                        {"option_id": f"o{n}b", "action_type": "do_nothing", "net_usd_mid": 0.0, "tier": "N0"}]}


def integrity(n: int, exp: float) -> dict:
    return {"issue_id": f"S030|sku_key_mismatch|SKU-I{n}", "kind": "sku_key_mismatch", "sku": f"SKU-I{n}",
            "category": "integrity", "integrity": True, "exposure_usd": exp, "severity_usd": 0.0,
            "data_caveats": [f"SKU-I{n} is written in another format."], "evidence": [], "options": []}


def line(sku: str, deadline: date | None, waste: float, lost: float, status: str = "ok") -> dict:
    return {"sku": sku, "name": sku, "supplier_id": "SUP01", "supplier_name": "Norte", "qty": 10, "cases": 1,
            "est_cost_usd": 7.1, "expected_delivery": "2026-03-13", "projected_stockout_date": "2026-03-11",
            "order_deadline": deadline.isoformat() if deadline else None, "order_deadline_status": status,
            "stockout_risk_without_order": 0.9, "expected_waste_usd": {"low": 0, "mid": waste, "high": 9},
            "expected_lost_sales_usd": {"low": 0, "mid": lost, "high": 9}, "sensitivity": {"0.6": 1},
            "basis": {"n_days": 55, "censored_share": 0.2}, "data_caveats": ["c" * 100],
            "issue": op_issue(900 + len(sku), 5.0)}


class RichMetrics(FakeMetrics):
    def __init__(self):
        super().__init__()
        self.counts: dict[str, int] = {}
        self.sleep = 0.0

    def _n(self, name):
        self.counts[name] = self.counts.get(name, 0) + 1
        if self.sleep:
            time.sleep(self.sleep)

    def kpis(self, store_id, as_of, date_from, date_to):
        self._n("kpis")
        out = super().kpis(store_id, as_of, date_from, date_to)
        return {**out, "transactions": 477, "tx_per_staff_hour": 1.83, "waste_usd": 1429.6,
                "lost_sales_usd": {"low": 37.0, "mid": 383.9, "high": 503.2}}

    def issues(self, store_id, as_of, limit=5):
        self._n("issues")
        pool = [op_issue(i, 100.0 - i * 10) for i in range(8)] + [integrity(i, 1000.0 * (i + 1)) for i in range(5)]
        return pool[:limit]

    def order_plan(self, store_id, as_of):
        self._n("order_plan")
        lines = [line("A", as_of, 1, 1), line("B", as_of, 2, 3), line("C", as_of + timedelta(days=1), 9, 9),
                 line("D", None, 0.5, 0.5, "deadline_passed"), line("E", as_of + timedelta(days=5), 4, 4),
                 line("F", as_of + timedelta(days=6), 3, 3), line("G", as_of + timedelta(days=7), 2, 2)]
        return {"store_id": store_id, "as_of": str(as_of), "lines": lines, "total_lines": len(lines)}

    def supplier_performance(self, store_id, as_of):
        self._n("suppliers")
        return [{"supplier_id": "SUP01", "supplier_name": "Norte", "on_time_pct": 93.6, "fill_pct": 100.0,
                 "next_delivery": "2026-03-11", "lead_time_mean_days": 1.1},
                {"supplier_id": "SUP02", "supplier_name": "Costa", "on_time_pct": 71.0, "fill_pct": 88.0,
                 "next_delivery": "2026-03-12"}]


@pytest.fixture
def env():
    metrics = RichMetrics()
    c = Container(metrics=metrics, core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(),
                  proposals=InMemoryProposals(), executions=InMemoryExecutions(), backtests=InMemoryBacktests(),
                  trace=InMemoryTrace(), clock=FakeClock())
    return TestClient(create_app(c)), c, metrics


def mkcase(client, day="2026-03-10"):
    return client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": day}).json()["case_id"]


def snap(client, cid, **h):
    r = client.get("/internal/v1/snapshot", headers={"X-Glazed-Case": cid, **h})
    assert r.status_code == 200, r.text
    return r.json()
