"""Cutoff discipline: the only door between history and forecasts."""
from __future__ import annotations

import pandas as pd

from forecast import baselines, glm

MAIN_MODEL = "glm_poisson"
ACTUAL_COLS = ["units", "censored", "inv_covered"]


def split_at_cutoff(panel: pd.DataFrame, cutoff):
    """Return (train, future). `future` keeps the schedule and known-in-advance covariates
    only: actuals and the inventory-derived flags are dropped."""
    cutoff = pd.Timestamp(cutoff)
    train = panel[panel["date"] <= cutoff].copy()
    future = panel[panel["date"] > cutoff].drop(columns=[c for c in ACTUAL_COLS if c in panel.columns]).copy()
    return train, future


def forecast_all(panel: pd.DataFrame, cutoff, half_life=None) -> pd.DataFrame:
    """Fit every model on data <= cutoff and forecast every future open store-day.
    Returns long frame: model, store_id, sku, date, forecast."""
    train, future = split_at_cutoff(panel, cutoff)
    frames = []
    for name, df in baselines.fit_baselines(train, cutoff).predict(future).items():
        frames.append(df.assign(model=name))
    frames.append(glm.fit_poisson(train, cutoff, half_life=half_life).predict(future).assign(model=MAIN_MODEL))
    out = pd.concat(frames, ignore_index=True)
    # only series every model can forecast, so comparisons are like-for-like
    n_models = out["model"].nunique()
    ok = out.groupby(["store_id", "sku", "date"])["model"].transform("nunique") == n_models
    return out[ok].reset_index(drop=True)[["model", "store_id", "sku", "date", "forecast"]]
