"""R4: /kpis (public and internal) compares the window with the same weekdays of the previous 8 weeks."""
from datetime import date, timedelta

from tests.unit.manager_support import AS_OF, build


class Metrics:
    """Wraps the scripted FakeMetrics.kpis: the current window (k = 0) differs from its predecessors (k >= 1)."""

    def __init__(self, empty_from_week=99):
        self.empty_from_week = empty_from_week

    def __call__(self, m):
        real = m.kpis

        def kpis(store_id, as_of, date_from, date_to):
            base = real(store_id, as_of, date_from, date_to)
            k = (AS_OF - date_to).days // 7 if date_to <= AS_OF else 0
            cur = date_to == AS_OF
            return {**base, "net_sales": 100.0 if cur else 50.0, "waste_usd": 0.0 if not cur else 10.0,
                    "tx_per_staff_hour": None if cur else 2.0, "units": 200 if cur else 100,
                    "lost_sales_usd": {"low": 1.0, "mid": 30.0 if cur else 20.0, "high": 50.0},
                    "days_with_data": 0 if (not cur and k >= self.empty_from_week) else (date_to - date_from).days + 1}
        m.kpis = kpis


def public(client, cid, **p):
    r = client.get(f"/api/v1/cases/{cid}/kpis", params=p)
    assert r.status_code == 200, r.text
    return r.json()


def test_baseline_is_the_mean_of_the_previous_8_same_weekday_windows_and_delta_is_a_percentage():
    client, cid, m = build(Metrics())
    k = public(client, cid)
    assert k["net_sales"] == 100.0 and k["baseline"]["net_sales"] == 50.0 and k["delta_pct"]["net_sales"] == 100.0
    assert k["baseline"]["weeks_used"] == 8 and k["baseline"]["lost_sales_usd"]["mid"] == 20.0
    assert k["delta_pct"]["lost_sales_usd"] == 50.0 and k["delta_pct"]["units"] == 100.0
    assert k["delta_pct"]["waste_usd"] is None  # a zero baseline has no percentage
    assert k["delta_pct"]["tx_per_staff_hour"] is None  # no current value
    windows = {(c[3], c[4]) for c in m.calls if c[0] == "kpis"}
    for w in range(1, 9):
        assert (AS_OF - timedelta(days=6 + 7 * w), AS_OF - timedelta(days=7 * w)) in windows


def test_the_window_length_is_kept_and_no_window_reads_past_as_of():
    client, cid, m = build(Metrics())
    client.container.briefings.wait_idle()
    m.calls.clear()  # the background briefing warm-up reads 7-day windows
    k = public(client, cid, date_from="2026-07-17", date_to="2026-07-19")
    assert k["baseline"]["weeks_used"] == 8
    spans = [(c[4] - c[3]).days for c in m.calls if c[0] == "kpis"]
    assert set(spans) == {2}
    assert all(c[4] <= AS_OF for c in m.calls if c[0] == "kpis")
    assert {c[3].isoweekday() for c in m.calls if c[0] == "kpis"} == {date(2026, 7, 17).isoweekday()}


def test_windows_without_data_are_skipped():
    client, cid, _ = build(Metrics(empty_from_week=5))
    k = public(client, cid)
    assert k["baseline"]["weeks_used"] == 4 and k["baseline"]["net_sales"] == 50.0


def test_no_history_means_no_baseline_and_no_delta():
    client, cid, _ = build(Metrics(empty_from_week=1))
    k = public(client, cid)
    assert k["baseline"] is None and k["delta_pct"] is None and k["net_sales"] == 100.0


def test_internal_kpis_carry_the_same_baseline():
    client, cid, _ = build(Metrics())
    k = client.get("/internal/v1/kpis", headers={"X-Glazed-Case": cid}).json()
    assert k["baseline"]["net_sales"] == 50.0 and k["delta_pct"]["net_sales"] == 100.0
    assert k["store_display_name"]
