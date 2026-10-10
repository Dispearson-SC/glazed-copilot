from datetime import date

import pytest

from glazed_backend.metrics.forecast import (empirical_quantiles, interpolate_quantile, same_weekday_dates,
                                              weekday_samples)


def test_same_weekday_dates_are_the_previous_eight_weeks():
    d = date(2026, 3, 10)
    got = same_weekday_dates(d)
    assert len(got) == 8 and got[0] == date(2026, 3, 3) and got[-1] == date(2026, 1, 13)


def test_weekday_samples_never_use_a_date_after_the_origin():
    by = {date(2026, 3, 3): 5.0, date(2026, 2, 24): 7.0, date(2026, 3, 10): 99.0}
    assert weekday_samples(by, date(2026, 3, 10), origin=date(2026, 3, 9)) == [5.0, 7.0]
    # a target far in the future: only the same-weekday dates <= origin that exist
    assert weekday_samples(by, date(2026, 3, 24), origin=date(2026, 3, 9)) == [5.0, 7.0]


def test_empirical_quantiles_of_eight_samples():
    q = empirical_quantiles([1, 2, 3, 4, 5, 6, 7, 8])
    assert q["p50"] == pytest.approx(4.5) and q["p10"] < q["p20"] < q["p50"] < q["p80"] < q["p90"]


def test_interpolate_quantile_linear_between_known_levels_and_clamped():
    lv = {0.1: 2.0, 0.5: 4.0, 0.9: 10.0}
    assert interpolate_quantile(lv, 0.74) == pytest.approx(4.0 + 0.6 * 6.0)
    assert interpolate_quantile(lv, 0.05) == 2.0 and interpolate_quantile(lv, 0.99) == 10.0
    assert interpolate_quantile({}, 0.5) is None
