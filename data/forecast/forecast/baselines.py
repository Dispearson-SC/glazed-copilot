"""Multi-step baselines anchored at the cutoff.

Both use only the last 28 training days (4 weeks per weekday). Censored (stockout) days
are ignored. For a horizon date d the forecast depends only on the weekday of d, so the
forecast for the whole holdout repeats the last observed week pattern.

* seasonal_naive : most recent valid value of the same weekday.
* ma28_weekday   : mean of the valid values of the same weekday in the last 28 days.
Fallback when a weekday has no valid value: mean of all valid values in the 28 days.
"""
from __future__ import annotations

import pandas as pd

from forecast.panel import KEY

SERIES = ["store_id", "sku"]
WINDOW = 28


def _check(train: pd.DataFrame, cutoff) -> None:
    if len(train) and train["date"].max() > pd.Timestamp(cutoff):
        raise ValueError("training data contains rows after cutoff")


class Baselines:
    def __init__(self, table: pd.DataFrame):
        self.table = table  # store_id, sku, dow, seasonal_naive, ma28_weekday

    def predict(self, future: pd.DataFrame) -> dict[str, pd.DataFrame]:
        f = future[KEY].copy()
        f["dow"] = f["date"].dt.dayofweek
        f = f.merge(self.table, on=SERIES + ["dow"], how="inner")
        out = {}
        for name in ("seasonal_naive", "ma28_weekday"):
            part = f[KEY + [name]].rename(columns={name: "forecast"}).dropna(subset=["forecast"])
            out[name] = part.reset_index(drop=True)
        return out


def fit_baselines(train: pd.DataFrame, cutoff) -> Baselines:
    _check(train, cutoff)
    cutoff = pd.Timestamp(cutoff)
    w = train[(train["date"] > cutoff - pd.Timedelta(days=WINDOW)) & ~train["censored"].astype(bool)].copy()
    w["dow"] = w["date"].dt.dayofweek
    w = w.sort_values(SERIES + ["date"])
    g = w.groupby(SERIES + ["dow"])["units"]
    per_dow = pd.DataFrame({"seasonal_naive": g.last(), "ma28_weekday": g.mean()}).reset_index()
    overall = w.groupby(SERIES)["units"].mean().rename("overall").reset_index()
    grid = overall.merge(pd.DataFrame({"dow": range(7)}), how="cross")
    tab = grid.merge(per_dow, on=SERIES + ["dow"], how="left")
    for c in ("seasonal_naive", "ma28_weekday"):
        tab[c] = tab[c].fillna(tab["overall"])
    return Baselines(tab.drop(columns="overall"))
