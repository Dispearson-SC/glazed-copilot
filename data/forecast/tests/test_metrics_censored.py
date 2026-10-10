import numpy as np
import pytest

from forecast import metrics as m
from forecast import panel as p


def test_pinball_censored_ignores_overforecast():
    # a sale on a stockout day is a lower bound on demand: only under-forecast is a miss
    a, f = [10, 10], [20, 4]
    assert m.pinball_censored(a, f, 0.74) == pytest.approx(0.74 * 6 / 2)


def test_censored_coverage_counts_forecast_ge_sale_as_covered():
    assert m.censored_coverage([10, 10, 10], [10, 30, 9]) == pytest.approx(2 / 3)


def test_censored_coverage_all_under():
    assert m.censored_coverage([5, 5], [1, 2]) == 0.0


def test_shelf_life_class_buckets():
    days = [1, 2, 3, 5, 730, np.nan, np.nan]
    perishable = [True, True, True, True, False, False, False]
    assert list(p.shelf_life_class(days, perishable)) == [
        "1d", "2-3d", "2-3d", "4-5d", "non-perishable", "non-perishable", "non-perishable",
    ]
