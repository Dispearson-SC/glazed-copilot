"""Forecast use cases. The forecaster supplies quantiles; this layer owns the no-look-ahead rules: actuals only for
dates <= as_of, metrics only over dates <= as_of with censored days excluded, and a forecast issued after as_of is
never shown."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from ..domain import DomainError, NotFound, Unprocessable
from ..metrics.accuracy import ScoredPoint, summarize
from ..metrics.forecast import weekday_samples
from ..metrics.types import SkuSeries
from ..ports.forecast import ForecastResult, ForecastRow

STORE_CENSOR_SHARE = 0.25  # a store day is censored when stockout SKUs account for this share of its USD sales
DEFAULT_PAST_DAYS, DEFAULT_AHEAD_DAYS = 27, 13
LOOKBACK_DAYS = 63  # history read before the first requested day: 8 same-weekday samples need 56
FLOW_LOOKBACK_DAYS = 70


def _r(x: float | None, nd: int = 4) -> float | None:
    return None if x is None else round(x, nd)


@dataclass
class Loaded:
    as_of: date
    history: list[SkuSeries]
    result: ForecastResult


class ForecastLoader:
    """History (never past as_of) plus the first admissible forecast: file model if issued <= as_of, else baseline."""

    def __init__(self, metrics, forecasters: list[Any]) -> None:
        self.metrics, self.forecasters = metrics, forecasters

    def load(self, store_id: str, as_of: date, sku: str | None, date_from: date, date_to: date) -> Loaded:
        start = min(date_from, as_of) - timedelta(days=LOOKBACK_DAYS)
        history = [SkuSeries(s.sku, s.price, s.shelf_life_days, tuple(r for r in s.rows if start <= r.date <= as_of))
                   for s in self.metrics.demand_history(store_id, as_of, sku, start)]  # clipped again: defence in depth
        if sku and not any(s.sku == sku for s in history):
            raise NotFound(f"sku {sku!r} has no history in store {store_id}")
        for f in self.forecasters:
            res = f.forecast(store_id, as_of, [sku] if sku else None, date_from, date_to, history)
            if res is not None and res.rows and res.origin <= as_of:
                return Loaded(as_of, history, res)
        raise NotFound(f"no forecast is available for {sku or 'the store'} between {date_from} and {date_to}")


def _levels(rows: list[ForecastRow], price: dict[str, float] | None) -> dict[str, float]:
    """Sum of the quantiles every row provides (store level sums SKUs: an upper-bound band, not an exact quantile)."""
    w = (lambda r: price[r.sku]) if price else (lambda r: 1.0)
    names = set.intersection(*(set(r.quantiles) | {"p50"} for r in rows))
    out = {}
    for n in ("p10", "p20", "p50", "p80", "p90"):
        if n in names:
            out[n] = sum((r.forecast if n == "p50" else r.quantiles[n]) * w(r) for r in rows)
    return out


class GetForecast:
    def __init__(self, cases, metrics, forecasters: list[Any]) -> None:
        self.cases, self.metrics, self.loader = cases, metrics, ForecastLoader(metrics, forecasters)

    def execute(self, case_id: str, sku: str | None = None, date_from: date | None = None, date_to: date | None = None,
                level: str | None = None) -> dict[str, Any]:
        from . import _case
        case = _case(self.cases, case_id)
        as_of = case.sim_today
        level = level or ("sku" if sku else "store")
        if level not in ("sku", "store"):
            raise DomainError("level must be 'sku' or 'store'")
        if level == "sku" and not sku:
            raise DomainError("sku is required for level=sku")
        if level == "store" and sku:
            raise DomainError("sku is only valid with level=sku")
        date_from = date_from or as_of - timedelta(days=DEFAULT_PAST_DAYS)
        date_to = date_to or as_of + timedelta(days=DEFAULT_AHEAD_DAYS)
        if date_from > date_to:
            raise DomainError("from must not be after to")
        loaded = self.loader.load(case.store_id, as_of, sku, date_from, date_to)
        points, scored = self._points(loaded, level == "store")
        res = loaded.result
        last = max((p["date"] for p in points), default=None)
        horizon = max(0, (date.fromisoformat(last) - res.origin).days) if last else 0
        return {"store_id": case.store_id, "sku": sku if level == "sku" else None, "level": level,
                "as_of": as_of.isoformat(), "forecast_origin": res.origin.isoformat(), "model": res.model,
                "model_version": res.model_version, "unit": "usd" if level == "store" else "units",
                "horizon_days": horizon, "points": points, "metrics_to_date": summarize(scored)}

    def _points(self, loaded: Loaded, store: bool) -> tuple[list[dict[str, Any]], list[ScoredPoint]]:
        as_of, res = loaded.as_of, loaded.result
        price = {s.sku: s.price for s in loaded.history}
        rows_by = {s.sku: {r.date: r for r in s.rows} for s in loaded.history}
        units_by = {k: {d: float(r.sold) for d, r in v.items()} for k, v in rows_by.items()}
        by_date: dict[date, list[ForecastRow]] = {}
        for r in res.rows:
            by_date.setdefault(r.date, []).append(r)
        points, scored = [], []
        for d in sorted(by_date):
            rows = [r for r in by_date[d] if r.sku in price]
            if not rows:
                continue
            w = {r.sku: (price[r.sku] if store else 1.0) for r in rows}
            lv = _levels(rows, w if store else None)
            base_parts = [(weekday_samples(units_by[r.sku], d, as_of), w[r.sku]) for r in rows]
            base = [sum(s) / len(s) * k for s, k in base_parts if s]
            baseline = sum(base) if base else None
            actual, censored = None, False
            if d <= as_of:  # NO LOOK-AHEAD: a date after as_of never has an actual, whatever the adapter returned
                seen = [(rows_by[r.sku][d], w[r.sku]) for r in rows if d in rows_by[r.sku]]
                if seen:
                    actual = sum(x.sold * k for x, k in seen)
                    hit = sum(x.sold * k for x, k in seen if x.stockout_hours > 0)
                    censored = (hit / actual >= STORE_CENSOR_SHARE if actual > 0 else False) if store \
                        else seen[0][0].stockout_hours > 0
            fc = sum(r.forecast * w[r.sku] for r in rows)
            pt = {"date": d.isoformat(), "forecast": _r(fc), "p10": _r(lv["p10"]), "p90": _r(lv["p90"]),
                  "baseline": _r(baseline), "actual": _r(actual), "censored": censored}
            if "p20" in lv or "p80" in lv:
                pt["quantiles"] = {k: _r(v) for k, v in lv.items()}
            points.append(pt)
            if actual is not None:
                scored.append(ScoredPoint(actual, fc, lv["p10"], lv["p90"], censored, baseline,
                                          tuple((q, lv[k]) for k, q in (("p20", 0.2), ("p80", 0.8)) if k in lv)))
        return points, scored


class ForecastAccuracy:
    """Accuracy over SKU-days with an actual, dates <= as_of only, grouped by shelf-life class, store format or SKU.
    Scored in units. Store scoped: the format grouping has one group, the format of the case's store."""

    BY = ("shelf_life", "format", "sku")
    DEFAULT_DAYS = 28

    def __init__(self, cases, metrics, forecasters: list[Any]) -> None:
        self.cases, self.metrics, self.loader = cases, metrics, ForecastLoader(metrics, forecasters)

    def execute(self, case_id: str, by: str | None, date_from: date | None = None, date_to: date | None = None) -> dict[str, Any]:
        from . import _case
        from ..metrics.accuracy import segment, shelf_life_class
        case = _case(self.cases, case_id)
        if by not in self.BY:
            raise DomainError(f"by must be one of {', '.join(self.BY)}")
        as_of = case.sim_today
        date_to = min(date_to or as_of, as_of)  # nothing after as_of can be scored
        date_from = date_from or date_to - timedelta(days=self.DEFAULT_DAYS - 1)
        if date_from > date_to:
            raise DomainError("from must not be after to")
        loaded = self.loader.load(case.store_id, as_of, None, date_from, date_to)
        fmt = next((s.get("format") for s in self.metrics.stores() if s["store_id"] == case.store_id), None) or "unknown"
        life = {s.sku: s.shelf_life_days for s in loaded.history}
        key = {"sku": lambda k: k, "shelf_life": lambda k: shelf_life_class(life.get(k)), "format": lambda k: fmt}[by]
        items = [(key(sku), p) for sku, p in self._sku_days(loaded, date_from, date_to)]
        return {"store_id": case.store_id, "by": by, "as_of": as_of.isoformat(), "window": {"from": date_from.isoformat(),
                "to": date_to.isoformat()}, "unit": "units", "model": loaded.result.model,
                "model_version": loaded.result.model_version, "forecast_origin": loaded.result.origin.isoformat(),
                "groups": segment(items), "overall": summarize([p for _, p in items])}

    @staticmethod
    def _sku_days(loaded: Loaded, date_from: date, date_to: date) -> list[tuple[str, ScoredPoint]]:
        rows_by = {s.sku: {r.date: r for r in s.rows} for s in loaded.history}
        units_by = {k: {d: float(r.sold) for d, r in v.items()} for k, v in rows_by.items()}
        out = []
        for fr in loaded.result.rows:
            actual_row = rows_by.get(fr.sku, {}).get(fr.date)
            if actual_row is None or not date_from <= fr.date <= min(date_to, loaded.as_of):  # NO LOOK-AHEAD
                continue
            s = weekday_samples(units_by[fr.sku], fr.date, loaded.as_of)
            lv = fr.levels()
            out.append((fr.sku, ScoredPoint(float(actual_row.sold), fr.forecast, fr.quantiles["p10"], fr.quantiles["p90"],
                                            actual_row.stockout_hours > 0, sum(s) / len(s) if s else None,
                                            tuple((q, lv[q]) for q in (0.2, 0.8) if q in lv))))
        return out


class DemandForecast:
    """One SKU, one future day, for the agents: p50 plus the quantile ladder. Levels the model does not provide are
    interpolated and named in `interpolated_quantiles`."""

    LADDER = ("p10", "p20", "p50", "p80", "p90")
    TRAINING_DAYS = 56

    def __init__(self, metrics, forecasters: list[Any]) -> None:
        self.loader = ForecastLoader(metrics, forecasters)

    def execute(self, case, sku: str, target_date: date) -> dict[str, Any]:
        from ..metrics.forecast import LEVELS
        as_of = case.sim_today
        if target_date <= as_of:
            raise Unprocessable(f"target_date {target_date} must be after the case date {as_of}")
        loaded = self.loader.load(case.store_id, as_of, sku, target_date, target_date)
        row = next((r for r in loaded.result.rows if r.sku == sku and r.date == target_date), None)
        if row is None:
            raise NotFound(f"no forecast for {sku} on {target_date}")
        have = {k for k in row.quantiles} | {"p50"}
        q = {k: round(row.quantile(LEVELS[k]), 4) for k in self.LADDER}
        series = next(s for s in loaded.history if s.sku == sku)
        window = [r for r in series.rows if loaded.result.origin - timedelta(days=self.TRAINING_DAYS) < r.date <= loaded.result.origin]
        share = sum(1 for r in window if r.stockout_hours > 0) / len(window) if window else 0.0
        out = {"sku": sku, "target_date": target_date.isoformat(), "qty": q["p50"],
               "qty_range": {k: q[k] for k in ("p10", "p50", "p90")}, "quantiles": q, "censored_share": round(share, 4),
               "weather_kind": "observed", "model": loaded.result.model, "model_version": loaded.result.model_version,
               "forecast_origin": loaded.result.origin.isoformat()}
        missing = [k for k in self.LADDER if k not in have]
        if missing:
            out["interpolated_quantiles"] = missing
        return out


class FlowForecast:
    """Store transactions, footfall and average ticket for a future day, from store daily data up to as_of."""

    def __init__(self, metrics, flow_forecaster) -> None:
        self.metrics, self.flow = metrics, flow_forecaster

    def execute(self, case, target_date: date) -> dict[str, Any]:
        as_of = case.sim_today
        if target_date <= as_of:
            raise Unprocessable(f"target_date {target_date} must be after the case date {as_of}")
        history = [r for r in self.metrics.flow_history(case.store_id, as_of, as_of - timedelta(days=FLOW_LOOKBACK_DAYS))
                   if r["date"] <= as_of]  # clipped again: NO LOOK-AHEAD whatever the adapter returned
        res = self.flow.flow(case.store_id, as_of, target_date, history)
        if res is None:
            raise NotFound(f"no flow data to forecast {target_date} for store {case.store_id}")
        return {"target_date": target_date.isoformat(), "granularity": res.granularity, "transactions": res.transactions,
                "footfall": res.footfall, "avg_ticket": res.avg_ticket, "model": res.model,
                "forecast_origin": res.origin.isoformat()}
