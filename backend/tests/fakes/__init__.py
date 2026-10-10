"""Fakes for every port. Repositories reuse the in-memory adapters."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from glazed_backend.adapters.driven.memory import (  # noqa: F401
    InMemoryAlerts, InMemoryBacktests, InMemoryCases, InMemoryExecutions, InMemoryProposals, InMemoryTrace,
)
from glazed_backend.domain import FutureDate
from glazed_backend.metrics.types import DayRow, SkuSeries


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
        self.observed = {"net_usd": 20.0, "window": ["2026-03-12", "2026-03-14"]}

    def _guard(self, as_of: date, d: date) -> None:
        if d > as_of:
            raise FutureDate(f"{d} > as_of {as_of}")

    series: list = []  # SkuSeries served by demand_history
    flow: list = []  # {date, transactions, footfall, net_sales} served by flow_history
    leak = False  # True: ignore as_of like a buggy adapter, so tests prove the service enforces no-look-ahead

    def demand_history(self, store_id, as_of, sku, start):
        self.calls.append(("demand_history", store_id, as_of, sku))
        out = []
        for s in self.series:
            if sku in (None, s.sku):
                out.append(SkuSeries(s.sku, s.price, s.shelf_life_days, tuple(
                    r for r in s.rows if r.date >= start and (self.leak or r.date <= as_of))))
        return out

    def flow_history(self, store_id, as_of, start):
        self.calls.append(("flow_history", store_id, as_of))
        return [dict(r) for r in self.flow if r["date"] >= start and (self.leak or r["date"] <= as_of)]

    # -- Wave 12 manager metrics inputs --------------------------------------------------------------------
    catalog: dict = {}  # sku -> {product_name, department, supplier_id, unit_cost, price, shelf_life_days}
    selling: set = set()  # SKUs with sales in the window
    profile: dict = {"format": "Shop-in-Shop", "region": "Northeast", "open_hours": 12.0}
    pos: list = []  # open_purchase_orders rows (served as-is; `leak` skips the as_of filter)
    suppliers_sched: list = []  # {supplier_id, supplier_name, delivery_days}
    promos: list = []  # promotions rows
    staff: list = []  # {store_id, date, transactions, staff_hours}
    projections: dict = {}  # sku -> inventory_projection override

    def store_profile(self, store_id):
        return dict(self.profile)

    def product_catalog(self, store_id):
        return {k: dict(v) for k, v in self.catalog.items()}

    def selling_skus(self, store_id, as_of, start):
        self.calls.append(("selling_skus", store_id, as_of))
        return set(self.selling)

    def delivery_inputs(self, store_id, as_of, until):
        self.calls.append(("delivery_inputs", store_id, as_of, until))
        return {"pos": [dict(p) for p in self.pos], "suppliers": [dict(s) for s in self.suppliers_sched]}

    def promotions(self, store_id, as_of):
        self.calls.append(("promotions", store_id, as_of))
        return [dict(p) for p in self.promos]

    def staffing_history(self, store_id, as_of, start):
        self.calls.append(("staffing_history", store_id, as_of))
        return {"format": self.profile["format"],
                "rows": [dict(r) for r in self.staff if r["date"] >= start and (self.leak or r["date"] <= as_of)]}

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
        self.calls.append(("inventory_projection", store_id, as_of, sku, horizon))
        return self.projections.get(sku, {"sku": sku, "as_of": str(as_of), "horizon": horizon,
                                          "projected_stockout_date": None})

    def order_plan(self, store_id, as_of):
        return {"store_id": store_id, "as_of": str(as_of), "method": "simple_v0", "lines": []}

    def supplier_performance(self, store_id, as_of):
        self.calls.append(("supplier_performance", store_id, as_of))
        return [{"supplier_id": "SUP01", "on_time_pct": 90.0}]

    def promo_evaluation(self, store_id, as_of, promo_id):
        return {"promo_id": promo_id, "confidence": "low"}

    def promo_audit(self, store_id, as_of, department, discount_pct):
        self.calls.append(("promo_audit", store_id, as_of, department, discount_pct))
        return {"department": department, "discount_pct": discount_pct, "verdict": "block", "recommendation": "do_nothing",
                "similar": [{"promo_id": "PR002"}, {"promo_id": "PR005"}], "alternative": {"promo_id": "PR009"}}

    def observed_outcome(self, store_id, as_of, action_type, params):
        self.calls.append(("observed_outcome", store_id, as_of, action_type))
        return self.observed

    history_weeks: list = []  # weekly rows served by history(); `leak` keeps weeks after as_of

    def history(self, store_id, as_of):
        return {"store_id": store_id, "as_of": str(as_of),
                "weeks": [dict(w) for w in self.history_weeks if self.leak or w["week_start"] <= str(as_of)]}

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


def make_series(sku: str, price: float, start: date, end: date, units, shelf_life=None, stockout=lambda d: 0.0,
                closing=lambda d: 5, received=lambda d: 0) -> SkuSeries:
    """A SKU with one DayRow per day in [start, end]; `units(d)` is the units sold that day."""
    from datetime import timedelta
    rows, d = [], start
    while d <= end:
        rows.append(DayRow(d, int(received(d)), int(units(d)), 0, int(closing(d)), float(stockout(d))))
        d += timedelta(days=1)
    return SkuSeries(sku, price, shelf_life, tuple(rows))
