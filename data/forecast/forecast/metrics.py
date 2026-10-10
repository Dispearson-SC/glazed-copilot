"""Forecast accuracy metrics. Callers must filter NaN rows before calling."""
from __future__ import annotations

import numpy as np


def _a(x):
    return np.asarray(x, dtype=float)


def wape(actual, forecast) -> float:
    """Weighted absolute percentage error: sum|a-f| / sum|a|."""
    a, f = _a(actual), _a(forecast)
    den = np.abs(a).sum()
    return float("nan") if den == 0 else float(np.abs(a - f).sum() / den)


def bias(actual, forecast) -> float:
    """Signed relative bias: sum(f-a) / sum(a). Positive = over-forecast."""
    a, f = _a(actual), _a(forecast)
    den = a.sum()
    return float("nan") if den == 0 else float((f - a).sum() / den)


def naive_scale(history, season: int = 7) -> float:
    """In-sample mean absolute seasonal-naive error (MASE denominator). NaN pairs skipped."""
    y = _a(history)
    if len(y) <= season:
        return float("nan")
    d = np.abs(y[season:] - y[:-season])
    d = d[~np.isnan(d)]
    return float("nan") if len(d) == 0 else float(d.mean())


def mase(actual, forecast, scale) -> float:
    """Mean of |a-f|/scale over rows whose scale is positive and finite."""
    a, f, s = _a(actual), _a(forecast), _a(scale)
    ok = np.isfinite(s) & (s > 0)
    if not ok.any():
        return float("nan")
    return float((np.abs(a[ok] - f[ok]) / s[ok]).mean())


def pinball(actual, quantile_forecast, q: float) -> float:
    """Mean pinball (quantile) loss at level q."""
    a, f = _a(actual), _a(quantile_forecast)
    d = a - f
    return float(np.maximum(q * d, (q - 1) * d).mean())


def coverage(actual, lower, upper) -> float:
    """Share of actuals inside [lower, upper] (inclusive)."""
    a, lo, hi = _a(actual), _a(lower), _a(upper)
    return float(((a >= lo) & (a <= hi)).mean())


def interval_summary(actual, lower, upper) -> dict:
    a, lo, hi = _a(actual), _a(lower), _a(upper)
    return {
        "coverage": coverage(a, lo, hi),
        "mean_width": float((hi - lo).mean()),
        "pinball_p10": pinball(a, lo, 0.1),
        "pinball_p90": pinball(a, hi, 0.9),
    }


def pinball_censored(sale, quantile_forecast, q: float) -> float:
    """Pinball loss on stockout days, where the sale only lower-bounds demand.
    Only under-forecast (forecast < sale) is penalised; forecast >= sale costs nothing."""
    a, f = _a(sale), _a(quantile_forecast)
    return float((q * np.maximum(a - f, 0.0)).mean())


def censored_coverage(sale, upper) -> float:
    """One-sided coverage on censored days: share where the forecast quantile >= observed sale."""
    a, u = _a(sale), _a(upper)
    return float((u >= a).mean())
