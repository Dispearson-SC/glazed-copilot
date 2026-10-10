import pandas as pd
import pytest

from forecast import evaluate as ev


def test_waste_at_fill_rate_interpolates_between_points():
    fr = pd.DataFrame(
        {
            "model": ["m"] * 3,
            "q": [0.5, 0.7, 0.9],
            "fill_rate": [0.90, 0.96, 0.99],
            "waste_units": [100.0, 200.0, 500.0],
            "lost_units": [10.0, 4.0, 1.0],
        }
    )
    out = ev.at_fill_rate(fr, 0.975)
    # between q=0.7 (0.96, 200) and q=0.9 (0.99, 500): halfway -> 350
    assert out.loc[out["model"] == "m", "waste_units"].iloc[0] == pytest.approx(350.0)


def test_at_fill_rate_nan_when_target_unreachable():
    fr = pd.DataFrame({"model": ["m"] * 2, "q": [0.5, 0.9], "fill_rate": [0.80, 0.90],
                       "waste_units": [1.0, 2.0], "lost_units": [1.0, 1.0]})
    assert pd.isna(ev.at_fill_rate(fr, 0.97)["waste_units"].iloc[0])
