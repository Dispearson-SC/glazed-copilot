import numpy as np
import pandas as pd
import pytest

from forecast import glm, models
from tests.helpers import synthetic_panel


def test_split_half_life():
    assert glm.split_half_life(7) == (7, 7)
    assert glm.split_half_life(None) == (None, None)
    assert glm.split_half_life((7, None)) == (7, None)


def test_level_tracks_recent_shift_while_weekday_profile_uses_long_window():
    panel = synthetic_panel(n_days=210, seed=2, stores=("S1",), skus=("A",))
    cutoff = pd.Timestamp("2026-07-12")
    late = panel["date"] > cutoff - pd.Timedelta(days=21)
    panel.loc[late, "units"] = panel.loc[late, "units"] * 2.0  # level shift in the last 3 weeks
    train, future = models.split_at_cutoff(panel, cutoff)
    m = glm.fit_poisson(train.loc[train["date"] <= cutoff], cutoff, half_life=(5, None))
    pred = m.predict(future).head(14)
    pred_dow = pred.assign(dow=pred["date"].dt.dayofweek).groupby("dow")["forecast"].mean()
    recent = train[train["date"] > cutoff - pd.Timedelta(days=21)]["units"].mean()
    assert pred["forecast"].mean() == pytest.approx(recent, rel=0.2)
    assert pred_dow[4] / pred_dow[0] == pytest.approx(1.5, rel=0.2)
