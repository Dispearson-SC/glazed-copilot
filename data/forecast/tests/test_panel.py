import pandas as pd
import pytest

from forecast import panel as p


def d(s):
    return pd.Timestamp(s)


def make_tables():
    dates = pd.date_range("2026-01-01", periods=10)
    sales = pd.DataFrame(
        {
            "date": [dates[0], dates[1], dates[1], dates[2], dates[3], dates[4]],
            "store_id": ["S1"] * 6,
            "sku": ["A", "A", "A", "A", "A", "A"],
            "units_sold": [3, 4, -1, 5, 2, 7],
            "is_return": [False, False, True, False, False, False],
            "promo_id": [None] * 6,
        }
    )
    inventory = pd.DataFrame(
        {
            "date": [dates[0], dates[1], dates[2], dates[3]],
            "store_id": ["S1"] * 4,
            "sku": ["A"] * 4,
            "units_sold": [3, 4, 5, 0],
            "stockout_hours": [0.0, 0.0, 6.0, 0.0],
        }
    )
    status = ["open"] * 10
    status[3] = "temporary_closure"  # day index 3 closed
    store_calendar = pd.DataFrame({"store_id": "S1", "date": dates, "status": status})
    return sales, inventory, store_calendar


def test_cutoff_is_80pct_point_of_span():
    dates = pd.date_range("2025-10-01", "2026-09-30")
    assert p.compute_cutoff(dates.min(), dates.max(), 0.8) == d("2026-07-19")


def test_cutoff_small_span():
    assert p.compute_cutoff(d("2026-01-01"), d("2026-01-10"), 0.8) == d("2026-01-08")


def test_shared_span_is_intersection():
    lo, hi = p.shared_span([(d("2025-10-01"), d("2026-09-30")), (d("2025-10-03"), d("2026-09-28"))])
    assert (lo, hi) == (d("2025-10-03"), d("2026-09-28"))


def test_panel_excludes_closed_store_days_even_with_sales():
    sales, inv, cal = make_tables()
    panel = p.build_panel(sales, inv, cal)
    assert d("2026-01-04") not in set(panel["date"])  # temp closure day, had a sale row
    assert (panel.groupby(["store_id", "sku"]).size() == 9).all()  # 10 days minus closed


def test_panel_zero_fills_open_days_after_first_sale_and_excludes_returns():
    sales, inv, cal = make_tables()
    panel = p.build_panel(sales, inv, cal).set_index("date")
    assert panel.loc["2026-01-02", "units"] == 4  # return of -1 excluded from demand
    assert panel.loc["2026-01-06", "units"] == 0  # open day with no sales row -> 0
    assert panel.loc["2026-01-10", "units"] == 0


def test_panel_starts_at_first_observed_day_of_series():
    sales, inv, cal = make_tables()
    sales = sales[sales["date"] >= d("2026-01-03")]
    inv = inv[inv["date"] >= d("2026-01-03")]
    panel = p.build_panel(sales, inv, cal)
    assert panel["date"].min() == d("2026-01-03")


def test_censored_flag_from_stockout_hours_and_coverage():
    sales, inv, cal = make_tables()
    panel = p.build_panel(sales, inv, cal).set_index("date")
    assert bool(panel.loc["2026-01-03", "censored"]) is True
    assert bool(panel.loc["2026-01-02", "censored"]) is False
    assert bool(panel.loc["2026-01-03", "inv_covered"]) is True
    # no inventory row for that day -> not covered, not flagged
    assert bool(panel.loc["2026-01-09", "inv_covered"]) is False
    assert bool(panel.loc["2026-01-09", "censored"]) is False


def test_sku_without_inventory_is_never_censored():
    sales, inv, cal = make_tables()
    inv = inv.iloc[0:0]
    panel = p.build_panel(sales, inv, cal)
    assert not panel["censored"].any()
    assert not panel["inv_covered"].any()


def test_promo_scope_features():
    dates = pd.date_range("2026-01-01", periods=4)
    panel = pd.DataFrame(
        {
            "store_id": ["S1"] * 4 + ["S2"] * 4,
            "sku": ["A"] * 8,
            "date": list(dates) * 2,
            "department": ["Beverage"] * 8,
            "category": ["Coffee & Tea"] * 8,
            "region": ["Northeast"] * 4 + ["Midwest"] * 4,
        }
    )
    promos = pd.DataFrame(
        {
            "promo_id": ["P1"],
            "promo_type": ["Percent Off"],
            "start_date": [d("2026-01-02")],
            "end_date": [d("2026-01-03")],
            "discount_pct": [20.0],
            "department": ["Beverage"],
            "category": ["Coffee & Tea"],
            "region_scope": ["Northeast"],
        }
    )
    out = p.add_promo_features(panel, promos)
    assert out["promo_pct"].tolist() == [0, 0.2, 0.2, 0, 0, 0, 0, 0]
    assert (out["promo_bundle"] == 0).all()
