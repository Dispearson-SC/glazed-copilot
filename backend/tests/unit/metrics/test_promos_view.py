from datetime import date, timedelta

import pytest

from glazed_backend.metrics.promos_view import in_window, promo_status, sort_promos

AS_OF = date(2026, 7, 19)


def d(n):
    return AS_OF + timedelta(days=n)


def test_status_boundaries_a_promo_ending_on_as_of_is_past():
    assert promo_status(d(-5), d(0), AS_OF) == "past"
    assert promo_status(d(-5), d(1), AS_OF) == "active"
    assert promo_status(d(0), d(3), AS_OF) == "active"
    assert promo_status(d(1), d(3), AS_OF) == "upcoming"
    assert promo_status(d(-30), d(-20), AS_OF) == "past"


def test_window_applies_days_to_past_and_upcoming_but_never_hides_active():
    assert in_window("past", d(-40), d(-14), AS_OF, 14) and not in_window("past", d(-40), d(-15), AS_OF, 14)
    assert in_window("upcoming", d(14), d(20), AS_OF, 14) and not in_window("upcoming", d(15), d(20), AS_OF, 14)
    assert in_window("active", d(-90), d(300), AS_OF, 1)


def test_sort_active_then_upcoming_then_past():
    items = [{"promo_id": "P1", "status": "past", "start_date": "2026-06-01", "end_date": "2026-07-01"},
             {"promo_id": "P2", "status": "upcoming", "start_date": "2026-07-30", "end_date": "2026-08-02"},
             {"promo_id": "P3", "status": "active", "start_date": "2026-07-10", "end_date": "2026-07-25"},
             {"promo_id": "P4", "status": "upcoming", "start_date": "2026-07-22", "end_date": "2026-08-02"},
             {"promo_id": "P5", "status": "past", "start_date": "2026-06-20", "end_date": "2026-07-10"}]
    assert [i["promo_id"] for i in sort_promos(items)] == ["P3", "P4", "P2", "P5", "P1"]
