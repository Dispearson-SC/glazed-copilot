from datetime import date, timedelta

import pytest

from glazed_backend.metrics.staffing import WINDOW_DAYS, productivity_p50, recommended_hours

AS_OF = date(2026, 7, 19)


def r(offset, tx, hours, store="S1"):
    return {"store_id": store, "date": AS_OF - timedelta(days=offset), "transactions": tx, "staff_hours": hours}


def test_p50_is_the_median_of_store_day_ratios():
    rows = [r(1, 100, 50), r(2, 100, 25), r(3, 100, 12.5), r(4, 100, 25, "S2"), r(5, 90, 30, "S2")]
    p50, n = productivity_p50(rows, AS_OF)
    assert p50 == pytest.approx(4.0) and n == 5  # ratios 2, 4, 8, 4, 3 -> median 4


def test_rows_after_as_of_older_than_the_window_or_without_hours_are_ignored():
    rows = [r(1, 100, 25), r(-1, 100, 1), r(WINDOW_DAYS, 100, 1), r(2, 100, 0), r(3, None, 10)]
    assert productivity_p50(rows, AS_OF) == (pytest.approx(4.0), 1)
    assert productivity_p50([], AS_OF) == (None, 0)


def test_recommended_hours_divides_the_transaction_range_by_the_benchmark():
    assert recommended_hours({"low": 80.0, "mid": 100.0, "high": 120.0}, 4.0) == {"low": 20.0, "mid": 25.0, "high": 30.0}
    assert recommended_hours({"low": 83.0, "mid": 100.0, "high": 121.0}, 3.0) == {"low": 27.7, "mid": 33.3, "high": 40.3}
