"""Prediction intervals and hyper-parameter choice from a backtest INSIDE the training span.

The origin is moved back by the holdout length, so the backtest mimics the real task
(fit on the early part, forecast the next block) without touching data after the cutoff.
Intervals are additive empirical residual quantiles per forecast-level bucket.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from forecast import metrics, models

EDGES = [0, 0.25, 0.5, 1, 2, 4, 8, 16, 32, np.inf]


def backtest(panel: pd.DataFrame, cutoff, horizon_days: int, half_life=None) -> pd.DataFrame:
    """Forecast the last `horizon_days` before `cutoff` from an earlier origin.
    `panel` must already end at cutoff. Censored actuals are dropped."""
    cutoff = pd.Timestamp(cutoff)
    if panel["date"].max() > cutoff:
        raise ValueError("backtest panel contains rows after cutoff")
    origin = cutoff - pd.Timedelta(days=horizon_days)
    fc = models.forecast_all(panel, origin, half_life=half_life)
    act = panel.loc[~panel["censored"].astype(bool), ["store_id", "sku", "date", "units"]]
    out = fc.merge(act, on=["store_id", "sku", "date"], how="inner").rename(columns={"units": "actual"})
    return out.reset_index(drop=True)


def residual_table(forecast, actual, edges=EDGES, lo=0.1, hi=0.9) -> pd.DataFrame:
    f = np.asarray(forecast, dtype=float)
    r = np.asarray(actual, dtype=float) - f
    rows = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (f >= a) & (f < b)
        if m.sum() == 0:
            continue
        rows.append(
            {"lower": a, "upper": b, "q_lo": float(np.quantile(r[m], lo)), "q_hi": float(np.quantile(r[m], hi)), "n": int(m.sum())}
        )
    return pd.DataFrame(rows)


def apply_interval(forecast, table: pd.DataFrame) -> pd.DataFrame:
    f = np.asarray(forecast, dtype=float)
    lo = np.full(len(f), np.nan)
    hi = np.full(len(f), np.nan)
    for r in table.itertuples(index=False):
        m = (f >= r.lower) & (f < r.upper)
        lo[m] = f[m] + r.q_lo
        hi[m] = f[m] + r.q_hi
    # forecasts outside the table fall back to the nearest bucket's quantiles
    miss = np.isnan(lo)
    if miss.any():
        edge = table.iloc[-1] if f[miss].mean() >= table.iloc[0]["upper"] else table.iloc[0]
        lo[miss] = f[miss] + edge["q_lo"]
        hi[miss] = f[miss] + edge["q_hi"]
    lo = np.maximum(lo, 0.0)
    hi = np.maximum(hi, lo)
    return pd.DataFrame({"p10": lo, "p90": hi})


def select_half_life(panel: pd.DataFrame, cutoff, candidates, horizon_days: int):
    """Pick the recency half-life with the lowest backtest WAPE of the GLM. Returns (best, scores)."""
    scores = {}
    for hl in candidates:
        bt = backtest(panel, cutoff, horizon_days, half_life=hl)
        bt = bt[bt["model"] == models.MAIN_MODEL]
        scores[hl] = metrics.wape(bt["actual"], bt["forecast"])
    best = min(scores, key=lambda k: scores[k])
    return best, scores


LEVELS = np.round(np.arange(0.01, 1.0, 0.01), 2)


class QuantileGrid:
    """Residual (actual - forecast) quantiles per forecast-level bucket, on a dense q grid."""

    def __init__(self, edges, levels, resid, counts):
        self.edges = np.asarray(edges, dtype=float)
        self.levels = np.asarray(levels, dtype=float)
        self.resid = resid  # (n_buckets, n_levels)
        self.counts = counts

    def to_frame(self) -> pd.DataFrame:
        df = pd.DataFrame(self.resid, columns=[f"q{int(round(l * 100)):02d}" for l in self.levels])
        df.insert(0, "upper", self.edges[1:])
        df.insert(0, "lower", self.edges[:-1])
        df["n"] = self.counts
        return df


def residual_grid(forecast, actual, edges=EDGES, levels=LEVELS, center: bool = False) -> QuantileGrid:
    """center=True removes each bucket's mean residual: location comes from the model, only the
    spread is learned from the backtest (the backtest window's demand drift is regime-specific)."""
    f = np.asarray(forecast, dtype=float)
    r = np.asarray(actual, dtype=float) - f
    nb = len(edges) - 1
    idx = np.clip(np.searchsorted(edges, f, side="right") - 1, 0, nb - 1)
    R = np.full((nb, len(levels)), np.nan)
    counts = np.zeros(nb, dtype=int)
    for b in range(nb):
        m = idx == b
        counts[b] = int(m.sum())
        if counts[b] >= 30:
            rb = r[m] - r[m].mean() if center else r[m]
            R[b] = np.quantile(rb, levels)
    ok = np.where(counts >= 30)[0]
    for b in range(nb):  # sparse buckets borrow the nearest populated one
        if b not in ok:
            R[b] = R[ok[np.argmin(np.abs(ok - b))]]
    return QuantileGrid(edges, levels, R, counts)


def quantile(forecast, grid: QuantileGrid, q: float) -> np.ndarray:
    """Quantile q (any level in (0,1)) of demand for each forecast value."""
    f = np.asarray(forecast, dtype=float)
    nb = len(grid.edges) - 1
    idx = np.clip(np.searchsorted(grid.edges, f, side="right") - 1, 0, nb - 1)
    per_bucket = np.array([np.interp(q, grid.levels, grid.resid[b]) for b in range(nb)])
    return np.maximum(f + per_bucket[idx], 0.0)


def nb_alpha_table(mu, y, edges=EDGES) -> pd.DataFrame:
    """Negative-binomial dispersion per bucket by moments: var = mu + alpha * mu^2."""
    mu = np.asarray(mu, dtype=float)
    y = np.asarray(y, dtype=float)
    rows = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (mu >= a) & (mu < b)
        if m.sum() == 0:
            continue
        num = ((y[m] - mu[m]) ** 2 - mu[m]).sum()
        den = (mu[m] ** 2).sum()
        rows.append({"lower": a, "upper": b, "alpha": float(max(num / den, 0.0)) if den > 0 else 0.0, "n": int(m.sum())})
    return pd.DataFrame(rows)


def apply_alpha(mu, table: pd.DataFrame) -> np.ndarray:
    mu = np.asarray(mu, dtype=float)
    out = np.full(len(mu), table["alpha"].iloc[-1])
    for r in table.itertuples(index=False):
        out[(mu >= r.lower) & (mu < r.upper)] = r.alpha
    return out
