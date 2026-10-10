"""Global Poisson regression with one fixed effect (level) per store-SKU series.

log mu[s,t] = a[s] + x[s,t] . b

* a[s]  : series level (closed form given b: Poisson MLE with offset x.b)
* x.b   : weekday x site type, weekday x department, holiday, school break x site type,
          planned promotion (percent-off depth, bundle flag). All are known in advance,
          so the multi-step forecast from the cutoff needs no lagged actuals.
* weights decay exponentially with age (half_life days) to track the level near the cutoff.
* censored (stockout) days are dropped from the fit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from forecast.panel import KEY

SERIES = ["store_id", "sku"]
MIN_TRAIN_DAYS = 28
PSEUDO = 0.1


def recency_weights(dates, cutoff, half_life) -> np.ndarray:
    dates = pd.to_datetime(pd.Series(dates))
    if not half_life:
        return np.ones(len(dates))
    age = (pd.Timestamp(cutoff) - dates).dt.days.to_numpy(dtype=float)
    return 0.5 ** (age / half_life)


def split_half_life(hl):
    """half_life may be a scalar (same decay for levels and coefficients) or (level_hl, coef_hl)."""
    if isinstance(hl, tuple):
        return hl
    return hl, hl


class Design:
    """Builds the shared-feature matrix with levels frozen at training time."""

    def __init__(self, site_types, departments):
        self.site_types = list(site_types)
        self.departments = list(departments)
        self.names = (
            [f"dow{d}_{s}" for s in self.site_types for d in range(7)]
            + [f"dow{d}_{k}" for k in self.departments for d in range(7)]
            + ["holiday"]
            + [f"school_{s}" for s in self.site_types]
            + ["promo_pct", "promo_bundle"]
        )

    def matrix(self, df: pd.DataFrame) -> np.ndarray:
        dow = df["dow"].to_numpy()
        st = df["site_type"].to_numpy()
        dep = df["department"].to_numpy()
        cols = []
        for s in self.site_types:
            m = st == s
            cols += [(m & (dow == d)).astype(np.float64) for d in range(7)]
        for k in self.departments:
            m = dep == k
            cols += [(m & (dow == d)).astype(np.float64) for d in range(7)]
        cols.append(df["is_holiday"].to_numpy(dtype=np.float64))
        sb = df["is_school_break"].to_numpy(dtype=np.float64)
        cols += [sb * (st == s) for s in self.site_types]
        cols.append(df["promo_pct"].to_numpy(dtype=np.float64))
        cols.append(df["promo_bundle"].to_numpy(dtype=np.float64))
        return np.column_stack(cols)


class PoissonModel:
    def __init__(self, design, beta, levels: pd.DataFrame, half_life):
        self.design = design
        self.beta = beta
        self.levels = levels  # store_id, sku, a
        self.half_life = half_life

    def coefficients(self) -> pd.Series:
        return pd.Series(self.beta, index=self.design.names)

    def predict(self, future: pd.DataFrame) -> pd.DataFrame:
        f = future.merge(self.levels, on=SERIES, how="inner")
        eta = f["a"].to_numpy() + self.design.matrix(f) @ self.beta
        out = f[KEY].copy()
        out["forecast"] = np.exp(np.clip(eta, -20, 8))
        return out.reset_index(drop=True)


def fit_poisson(train: pd.DataFrame, cutoff, half_life=None, ridge: float = 1.0, iters: int = 12) -> PoissonModel:
    cutoff = pd.Timestamp(cutoff)
    if len(train) and train["date"].max() > cutoff:
        raise ValueError("training data contains rows after cutoff")
    d = train.loc[~train["censored"].astype(bool)].copy()
    counts = d.groupby(SERIES)["units"].transform("size")
    d = d.loc[counts >= MIN_TRAIN_DAYS].reset_index(drop=True)
    design = Design(sorted(d["site_type"].dropna().unique()), sorted(d["department"].dropna().unique()))
    X = design.matrix(d)
    y = d["units"].to_numpy(dtype=np.float64)
    hl_level, hl_coef = split_half_life(half_life)
    w = recency_weights(d["date"], cutoff, hl_coef)  # stage 1: coefficients (and provisional levels)
    wc = w
    wl = recency_weights(d["date"], cutoff, hl_level)  # stage 2: levels with coefficients frozen
    codes = d.groupby(SERIES, sort=True).ngroup().to_numpy()
    n_s = codes.max() + 1
    wy = np.bincount(codes, weights=w * y, minlength=n_s)
    a = np.log((wy + PSEUDO) / (np.bincount(codes, weights=w, minlength=n_s) + PSEUDO))
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = a[codes] + X @ b
        mu = np.exp(np.clip(eta, -20, 8))
        wm = wc * mu
        H = (X * wm[:, None]).T @ X + ridge * np.eye(X.shape[1])
        g = X.T @ (wc * (y - mu)) - ridge * b
        step = np.linalg.solve(H, g)
        b = b + np.clip(step, -1.0, 1.0)
        xb = np.exp(np.clip(X @ b, -20, 8))
        a = np.log((wy + PSEUDO) / (np.bincount(codes, weights=w * xb, minlength=n_s) + PSEUDO))
    if hl_level != hl_coef:
        xb = np.exp(np.clip(X @ b, -20, 8))
        wy_l = np.bincount(codes, weights=wl * y, minlength=n_s)
        a = np.log((wy_l + PSEUDO) / (np.bincount(codes, weights=wl * xb, minlength=n_s) + PSEUDO))
    keys = d.groupby(SERIES, sort=True).size().reset_index()[SERIES]
    levels = keys.assign(a=a)
    return PoissonModel(design, b, levels, half_life)
