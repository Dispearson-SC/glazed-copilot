"""ForecastPort adapters: a Parquet file produced by the holdout-forecast job, and a baseline fallback."""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import duckdb

from ...metrics.forecast import empirical_quantiles, weekday_samples
from ...metrics.types import SkuSeries
from ...ports.forecast import FlowResult, ForecastResult, ForecastRow

BASELINE_MODEL = "baseline-weekday-8w"
MIN_SAMPLES = 3
HOLDOUT_ORIGIN = date(2026, 7, 19)


class _Quantiles:
    """`quantile(q)` for any forecaster: exact when the model provides the level, interpolated otherwise."""

    def forecast(self, *a: Any, **k: Any) -> ForecastResult | None:  # pragma: no cover - overridden
        raise NotImplementedError

    def quantile(self, store_id: str, as_of: date, sku: str, target_date: date, q: float,
                 history: list[SkuSeries]) -> float | None:
        res = self.forecast(store_id, as_of, [sku], target_date, target_date, history)
        row = next((r for r in (res.rows if res else []) if r.sku == sku and r.date == target_date), None)
        return row.quantile(q) if row else None


class BaselineForecast(_Quantiles):
    """forecast = the same-weekday average of the previous 8 weeks; p10..p90 are the empirical quantiles of those
    samples. The origin is the last data day <= as_of (min(as_of, data cutoff)) and nothing later is read."""

    def forecast(self, store_id: str, as_of: date, skus: list[str] | None, date_from: date, date_to: date,
                 history: list[SkuSeries]) -> ForecastResult | None:
        series = [s for s in history if skus is None or s.sku in skus]
        days = [r.date for s in series for r in s.rows if r.date <= as_of]
        if not days:
            return None
        origin = max(days)
        rows: list[ForecastRow] = []
        for s in series:
            by = {r.date: float(r.sold) for r in s.rows if r.date <= origin}
            d = date_from
            while d <= date_to:
                samples = weekday_samples(by, d, origin)
                if len(samples) >= MIN_SAMPLES:
                    rows.append(ForecastRow(s.sku, d, sum(samples) / len(samples), empirical_quantiles(samples)))
                d += timedelta(days=1)
        return ForecastResult(BASELINE_MODEL, "1", origin, rows)


class FileForecast(_Quantiles):
    """Reads `{store_id, sku, date, forecast, p10, p90, actual, censored, model}` and, when present, `p20, p50, p80`,
    `mu`, `alpha`, `forecast_origin`, `model_version`. `actual` and `censored` are ignored here: the application takes
    them from the data, where the no-look-ahead rule is enforced. The job's origin is fixed (2026-07-19) unless the
    file says otherwise."""

    OPTIONAL_Q = ("p20", "p50", "p80")
    PARAMS = ("mu", "alpha")

    def __init__(self, path: str, origin: date = HOLDOUT_ORIGIN, model_version: str = "file") -> None:
        self.path, self.origin, self.model_version = path, origin, model_version

    def forecast(self, store_id: str, as_of: date, skus: list[str] | None, date_from: date, date_to: date,
                 history: list[SkuSeries]) -> ForecastResult | None:
        if not os.path.exists(self.path):
            return None
        try:
            con = duckdb.connect()
            cols = {r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [self.path]).fetchall()}
            if not {"store_id", "sku", "date", "forecast", "p10", "p90"} <= cols:
                return None
            sql = "SELECT * REPLACE (CAST(date AS DATE) AS date) FROM read_parquet(?) WHERE store_id=? AND date BETWEEN ? AND ?"
            args: list[Any] = [self.path, store_id, date_from, date_to]
            if skus:
                sql += f" AND sku IN ({', '.join('?' * len(skus))})"
                args += list(skus)
            cur = con.execute(sql + " ORDER BY sku, date", args)
            names = [c[0] for c in cur.description]
            data = [dict(zip(names, r)) for r in cur.fetchall()]
        except Exception:  # noqa: BLE001 - an unreadable file means "no file forecast": the caller falls back
            return None
        rows = []
        for r in data:
            q = {"p10": float(r["p10"]), "p90": float(r["p90"])}
            q.update({k: float(r[k]) for k in self.OPTIONAL_Q if k in r and r[k] is not None})
            extra = {k: float(r[k]) for k in self.PARAMS if k in r and r[k] is not None}
            rows.append(ForecastRow(r["sku"], r["date"], float(q.get("p50", r["forecast"])), q, extra))
        first = data[0] if data else {}
        origin = first.get("forecast_origin") or self.origin
        return ForecastResult(first.get("model") or "file-forecast", str(first.get("model_version") or self.model_version),
                              origin, rows)


class WeekdayFlow:
    """Daily transactions, footfall and average ticket: the same weekday over the last 8 weeks up to as_of, with the
    empirical p10/p50/p90 of those samples. A measure with no data in the window is null."""

    MODEL = "flow-weekday-8w"

    def flow(self, store_id: str, as_of: date, target_date: date, history: list[dict[str, Any]]) -> FlowResult | None:
        rows = [r for r in history if r["date"] <= as_of]
        if not rows:
            return None
        origin = max(r["date"] for r in rows)
        same = sorted((r for r in rows if r["date"].isoweekday() == target_date.isoweekday()), key=lambda r: r["date"])[-8:]

        def band(values: list[float]) -> dict[str, float] | None:
            if len(values) < MIN_SAMPLES:
                return None
            q = empirical_quantiles(values)
            return {k: round(q[k], 2) for k in ("p10", "p50", "p90")}

        tx = band([float(r["transactions"]) for r in same if r.get("transactions") is not None])
        if tx is None:
            return None
        foot = band([float(r["footfall"]) for r in same if r.get("footfall") is not None])
        ticket = band([r["net_sales"] / r["transactions"] for r in same if r.get("transactions") and r.get("net_sales") is not None])
        return FlowResult(self.MODEL, origin, "daily", tx, foot, ticket)
