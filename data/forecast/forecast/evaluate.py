"""Holdout evaluation: accuracy tables, censored-day scoring and a simple reorder simulation."""
from __future__ import annotations

import numpy as np
import pandas as pd

from forecast import metrics

Q_SERVICE = 0.74  # critical ratio used by reorder


def series_scale(train: pd.DataFrame) -> pd.DataFrame:
    """MASE denominator per series: mean |y_t - y_{t-7 days}| on non-censored training days."""
    t = train[["store_id", "sku", "date", "units", "censored"]].copy()
    t["y"] = t["units"].where(~t["censored"].astype(bool))
    lag = t[["store_id", "sku", "date", "y"]].copy()
    lag["date"] = lag["date"] + pd.Timedelta(days=7)
    m = t.merge(lag, on=["store_id", "sku", "date"], suffixes=("", "_lag"))
    m["d"] = (m["y"] - m["y_lag"]).abs()
    s = m.groupby(["store_id", "sku"])["d"].mean().rename("scale").reset_index()
    return s


def summarize(df: pd.DataFrame, q: float = Q_SERVICE) -> dict:
    """Metrics for one model on one slice. Uncensored rows give the accuracy metrics;
    censored (stockout) rows are scored one-sided and reported separately."""
    qcol = f"p{int(round(q * 100))}"
    u = df[~df["censored"].astype(bool)]
    c = df[df["censored"].astype(bool)]
    out = {
        "n": int(len(u)),
        "actual_units": float(u["actual"].sum()),
        "wape": metrics.wape(u["actual"], u["forecast"]) if len(u) else np.nan,
        "bias": metrics.bias(u["actual"], u["forecast"]) if len(u) else np.nan,
        "mase": metrics.mase(u["actual"], u["forecast"], u["scale"]) if len(u) else np.nan,
        f"pinball_{qcol}": metrics.pinball(u["actual"], u[qcol], q) if len(u) else np.nan,
        "cov_p10_p90": metrics.coverage(u["actual"], u["p10"], u["p90"]) if len(u) else np.nan,
        "n_censored": int(len(c)),
        f"cens_cov_{qcol}": metrics.censored_coverage(c["actual"], c[qcol]) if len(c) else np.nan,
        f"cens_pinball_{qcol}": metrics.pinball_censored(c["actual"], c[qcol], q) if len(c) else np.nan,
    }
    return out


def group_summary(df: pd.DataFrame, by, q: float = Q_SERVICE) -> pd.DataFrame:
    by = [by] if isinstance(by, str) else list(by)
    rows = []
    for key, g in df.groupby(["model"] + by, observed=True):
        key = key if isinstance(key, tuple) else (key,)
        rows.append({**dict(zip(["model"] + by, key)), **summarize(g, q)})
    return pd.DataFrame(rows)


def simulate_policy(df: pd.DataFrame) -> dict:
    """Daily order-up-to simulation per series-day with stock level S (units on the shelf).

    Assumptions (estimate, not a measurement): full replenishment to S every day, no
    carry-over credit; scored only on non-censored days where the sale equals demand;
    lost sales = max(0, demand - S); leftover = max(0, S - demand); leftover of perishable
    items (shelf class 1d, 2-3d, 4-5d) is waste, non-perishable leftover is carried (overstock only).
    """
    u = df[~df["censored"].astype(bool)]
    short = np.maximum(u["actual"] - u["S"], 0.0)
    left = np.maximum(u["S"] - u["actual"], 0.0)
    perish = (u["shelf_class"] != "non-perishable").to_numpy()
    waste = np.where(perish, left, 0.0)
    total = u["actual"].sum()
    return {
        "lost_units": float(short.sum()),
        "waste_units": float(waste.sum()),
        "overstock_units": float(left.sum()),
        "lost_value": float((short * u["price"]).sum()),
        "waste_cost": float((waste * u["cost"]).sum()),
        "fill_rate": float(1 - short.sum() / total) if total else np.nan,
    }


def at_fill_rate(frontier: pd.DataFrame, target: float) -> pd.DataFrame:
    """Per model, interpolate the sweep (q -> fill rate, waste, lost) at a target fill rate.
    NaN when the target lies outside the swept range."""
    rows = []
    for model, g in frontier.groupby("model"):
        g = g.sort_values("fill_rate")
        x = g["fill_rate"].to_numpy()
        ok = x.min() <= target <= x.max()
        row = {"model": model, "target_fill_rate": target}
        for col in ("q", "waste_units", "lost_units", "waste_cost", "lost_value", "overstock_units"):
            if col in g:
                row[col] = float(np.interp(target, x, g[col].to_numpy())) if ok else np.nan
        rows.append(row)
    return pd.DataFrame(rows)
