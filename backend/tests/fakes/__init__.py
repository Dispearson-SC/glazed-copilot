"""Fakes for every port. Repositories reuse the in-memory adapters."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from glazed_backend.adapters.driven.memory import (  # noqa: F401
    InMemoryAlerts, InMemoryBacktests, InMemoryCases, InMemoryExecutions, InMemoryProposals, InMemoryTrace,
)
from glazed_backend.domain import FutureDate


class FakeClock:
    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._now


class FakeMetrics:
    """Deterministic MetricsPort. Records calls so tests can assert as_of enforcement."""

    def __init__(self, issues_by_date: dict[date, list[dict]] | None = None) -> None:
        self.calls: list[tuple] = []
        self.issues_by_date = issues_by_date or {}

    def _guard(self, as_of: date, d: date) -> None:
        if d > as_of:
            raise FutureDate(f"{d} > as_of {as_of}")

    def stores(self):
        return [{"store_id": "S030", "name": "Gate Area West", "format": "Shop-in-Shop", "site_id": "ST12",
                 "region": "Northeast", "site_name": "Bayfront Municipal Airport", "site_type": "Airport",
                 "display_name": "Bayfront Municipal Airport · Gate Area West"}]

    def kpis(self, store_id, as_of, date_from, date_to):
        self._guard(as_of, date_to)
        self.calls.append(("kpis", store_id, as_of, date_from, date_to))
        return {"store_id": store_id, "net_sales": 1000.0, "date_from": str(date_from), "date_to": str(date_to),
                "waste_usd": 12.0, "lost_sales_usd": {"low": 1.0, "mid": 2.0, "high": 3.0}}

    def day_summary(self, store_id, as_of, day):
        self._guard(as_of, day)
        self.calls.append(("day_summary", store_id, as_of, day))
        return {"store_id": store_id, "date": str(day), "net_sales": 500.0}

    def issues(self, store_id, as_of, limit=5):
        self.calls.append(("issues", store_id, as_of, limit))
        return self.issues_by_date.get(as_of, [])[:limit]

    def inventory_projection(self, store_id, as_of, sku, horizon=7):
        return {"sku": sku, "as_of": str(as_of), "horizon": horizon}

    def order_plan(self, store_id, as_of):
        return {"store_id": store_id, "as_of": str(as_of), "method": "simple_v0", "lines": []}

    def supplier_performance(self, store_id, as_of):
        return [{"supplier_id": "SUP01", "on_time_pct": 90.0}]

    def promo_evaluation(self, store_id, as_of, promo_id):
        return {"promo_id": promo_id, "confidence": "low"}

    def history(self, store_id, as_of):
        return {"as_of": str(as_of)}

    def backtest_day(self, store_id, day, policy):
        self.calls.append(("backtest_day", store_id, day, policy))
        return {"current": {"waste_usd": 10.0, "lost_sales_usd": 20.0},
                "policy": {"waste_usd": 6.0, "lost_sales_usd": 15.0}}


class FakeCore:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.sent: list[tuple[str, str, str]] = []
        self.turns: dict[str, dict[str, Any]] = {}
        self.transcript: list[dict[str, Any]] = []

    def create_conversation(self, case_id, store_id):
        self.created.append(case_id)
        return f"conv-{case_id}"

    def send_turn(self, conversation_id, store_id, text):
        self.sent.append((conversation_id, store_id, text))
        tid = f"turn-{len(self.sent)}"
        self.turns[tid] = {"turn_id": tid, "status": "finished", "text": f"echo: {text}"}
        return tid

    def get_turn(self, turn_id, store_id):
        return self.turns[turn_id]

    def list_transcript(self, conversation_id, store_id):
        return list(self.transcript)
