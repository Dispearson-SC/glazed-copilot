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
                once = {(r.sku, r.date): r for r in res.rows}  # a SKU-day counts once, whatever the adapter returned
                if len(once) != len(res.rows):
                    res = ForecastResult(res.model, res.model_version, res.origin, list(once.values()))
                return Loaded(as_of, history, res)
        raise NotFound(f"no forecast is available for {sku or 'the store'} between {date_from} and {date_to}")


CALIBRATION_DAYS, MIN_CALIBRATION_DAYS = 28, 7
Z = {"p10": 1.2815515655446004, "p20": 0.8416212335729143, "p80": 0.8416212335729143, "p90": 1.2815515655446004}


def calibration_factor(history: list[SkuSeries], net_sales: dict[date, float], origin: date) -> dict[str, Any] | None:
    """Σ store net_sales / Σ(units x list price) over the 28 days up to the forecast origin. Units x list price ignores
    discounts and returns and the SKUs outside the inventory table, so it is not the store's USD: this puts the SKU-level
    model on the scale of store_daily_kpis.net_sales. None when the overlap is too short to trust."""
    start = origin - timedelta(days=CALIBRATION_DAYS - 1)
    value: dict[date, float] = {}
    for s in history:
        for r in s.rows:
            if start <= r.date <= origin:
                value[r.date] = value.get(r.date, 0.0) + r.sold * s.price
    days = [d for d in value if d in net_sales and start <= d <= origin and value[d] > 0]
    if len(days) < MIN_CALIBRATION_DAYS:
        return None
    sold, net = sum(value[d] for d in days), sum(net_sales[d] for d in days)
    return {"factor": net / sold, "days": len(days), "window": {"from": start.isoformat(), "to": origin.isoformat()}} \
        if sold > 0 and net > 0 else None


def store_levels(rows: list[ForecastRow], weight: dict[str, float]) -> dict[str, float]:
    """Store quantiles from SKU rows: the centre is the sum of the p50s; the spread is sqrt(sum of the SKU variances)
    (SKU demand taken as independent), each side from its own p50-p10 / p90-p50 distance. Summing SKU quantiles would
    assume every SKU lands at its p90 on the same day."""
    centre = sum(r.forecast * weight[r.sku] for r in rows)
    lo = sum(((r.forecast - r.quantiles["p10"]) / Z["p10"] * weight[r.sku]) ** 2 for r in rows) ** 0.5
    hi = sum(((r.quantiles["p90"] - r.forecast) / Z["p90"] * weight[r.sku]) ** 2 for r in rows) ** 0.5
    out = {"p10": max(0.0, centre - Z["p10"] * lo), "p50": centre, "p90": centre + Z["p90"] * hi}
    if all("p20" in r.quantiles or "p80" in r.quantiles for r in rows):
        out["p20"], out["p80"] = max(0.0, centre - Z["p20"] * lo), centre + Z["p80"] * hi
    return dict(sorted(out.items(), key=lambda kv: kv[1]))


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
        store_view = level == "store"
        net = self.metrics.store_net_sales(case.store_id, as_of, as_of - timedelta(days=LOOKBACK_DAYS + 56)) if store_view else {}
        net = {d: v for d, v in net.items() if d <= as_of}  # defence in depth: nothing after the case date is read
        calib = calibration_factor(loaded.history, net, loaded.result.origin) if store_view else None
        points, scored = self._points(loaded, store_view, net, calib["factor"] if calib else 1.0)
        res = loaded.result
        last = max((p["date"] for p in points), default=None)
        horizon = max(0, (date.fromisoformat(last) - res.origin).days) if last else 0
        return {"store_id": case.store_id, "sku": sku if level == "sku" else None, "level": level,
                "as_of": as_of.isoformat(), "forecast_origin": res.origin.isoformat(), "model": res.model,
                "model_version": res.model_version, "unit": "usd" if level == "store" else "units",
                "horizon_days": horizon, "points": points, "metrics_to_date": summarize(scored),
                **({"calibration": calib, "band_method": "sqrt_sum_of_sku_variances"} if store_view else {})}

    def _points(self, loaded: Loaded, store: bool, net: dict[date, float] | None = None,
                k: float = 1.0) -> tuple[list[dict[str, Any]], list[ScoredPoint]]:
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
            if store:
                cw = {sku: v * k for sku, v in w.items()}
                lv = store_levels(rows, cw)
                samples = weekday_samples(net or {}, d, as_of)  # == day-summary vs_same_weekday_avg on net_sales
                if samples:
                    baseline = sum(samples) / len(samples)
                else:
                    parts = [(weekday_samples(units_by[r.sku], d, as_of), cw[r.sku]) for r in rows]
                    base = [sum(s) / len(s) * kk for s, kk in parts if s]
                    baseline = sum(base) if base else None
            else:
                lv = _levels(rows, None)
                base = [sum(s) / len(s) for s in (weekday_samples(units_by[r.sku], d, as_of) for r in rows) if s]
                baseline = sum(base) if base else None
            actual, censored = None, False
            if d <= as_of:  # NO LOOK-AHEAD: a date after as_of never has an actual, whatever the adapter returned
                seen = [(rows_by[r.sku][d], w[r.sku]) for r in rows if d in rows_by[r.sku]]
                if seen:
                    actual = sum(x.sold * kk for x, kk in seen)
                    hit = sum(x.sold * kk for x, kk in seen if x.stockout_hours > 0)
                    censored = (hit / actual >= STORE_CENSOR_SHARE if actual > 0 else False) if store \
                        else seen[0][0].stockout_hours > 0
                    if store and net and d in net:
                        actual = net[d]  # the store's real net sales, not units x list price
            fc = lv["p50"] if store else sum(r.forecast * w[r.sku] for r in rows)
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
