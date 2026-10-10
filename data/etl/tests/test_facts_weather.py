from datetime import date

from glazed_etl import validate
from tests.helpers import make_world, rows
from tests.test_dimensions_core import _log_has


def W(d, tmax="20.0", tmin="12.0", precip="0", site="ST01"):
    return {"site_id": site, "date": d, "temp_max_c": tmax, "temp_min_c": tmin, "precip_mm": precip}


def wx(tmp_path, ws):
    return make_world(tmp_path, weather_daily=ws)


def test_weather_typed_and_clean_rows_untouched(tmp_path):
    con, log = wx(tmp_path, [W("2026-01-01"), W("2026-01-02", "21.5", "13.5", "1.2")])
    assert rows(con, "select site_id, date, temp_max_c, temp_min_c, precip_mm, temp_imputed, dq_flags from weather_daily order by date") == [
        ("ST01", date(2026, 1, 1), 20.0, 12.0, 0.0, False, None),
        ("ST01", date(2026, 1, 2), 21.5, 13.5, 1.2, False, None)]
    assert _log_has(log, "weather_daily", "WX01", "excluded", 0)


def test_weather_exact_duplicates_excluded(tmp_path):
    con, log = wx(tmp_path, [W("2026-01-01"), W("2026-01-01"), W("2026-01-02")])
    assert rows(con, "select count(*) from weather_daily") == [(2,)]
    assert _log_has(log, "weather_daily", "WX01", "excluded", 1)


def test_weather_ids_and_dates_normalized_orphans_excluded(tmp_path):
    con, log = wx(tmp_path, [W("01/02/2026", site=" st01 "), W("2026-01-03", site="ST99"), W("not a date")])
    assert rows(con, "select site_id, date from weather_daily") == [("ST01", date(2026, 1, 2))]
    assert _log_has(log, "weather_daily", "WX00", "excluded", 2)


def test_weather_sentinel_interpolated_between_neighbours(tmp_path):
    con, log = wx(tmp_path, [
        W("2026-01-01", "10.0", "2.0"), W("2026-01-02", "-999", "-999"), W("2026-01-03", "-999", "-999"),
        W("2026-01-04", "16.0", "8.0")])
    got = rows(con, "select date, temp_max_c, temp_min_c, temp_imputed, dq_flags from weather_daily order by date")
    assert got[1] == (date(2026, 1, 2), 12.0, 4.0, True, "temp_imputed")
    assert got[2] == (date(2026, 1, 3), 14.0, 6.0, True, "temp_imputed")
    assert got[0][3] is False and got[3][3] is False
    assert _log_has(log, "weather_daily", "WX02", "fixed", 2)


def test_weather_sentinel_at_edge_uses_single_neighbour(tmp_path):
    con, log = wx(tmp_path, [W("2026-01-01", "-999", "-999"), W("2026-01-02", "18.0", "10.0"),
                             W("2026-01-03", "19.0", "11.0"), W("2026-01-04", "-999", "-999")])
    assert rows(con, "select temp_max_c, temp_min_c from weather_daily order by date") == [
        (18.0, 10.0), (18.0, 10.0), (19.0, 11.0), (19.0, 11.0)]


def test_weather_interpolation_stays_within_site(tmp_path):
    con, _ = make_world(tmp_path, sites=[{"site_id": "ST01"}, {"site_id": "ST02"}], weather_daily=[
        W("2026-01-01", "10.0", "2.0"), W("2026-01-02", "-999", "-999"), W("2026-01-03", "14.0", "6.0"),
        W("2026-01-01", "30.0", "22.0", site="ST02"), W("2026-01-02", "30.0", "22.0", site="ST02")])
    assert rows(con, "select temp_max_c from weather_daily where site_id = 'ST01' and date = '2026-01-02'") == [(12.0,)]


def test_weather_all_temps_missing_stay_null_and_flagged(tmp_path):
    con, log = wx(tmp_path, [W("2026-01-01", "-999", "-999"), W("2026-01-02", "-999", "-999")])
    assert rows(con, "select temp_max_c, temp_min_c, temp_imputed, dq_flags from weather_daily limit 1") == [
        (None, None, False, "temp_unknown")]
    assert _log_has(log, "weather_daily", "WX05", "flagged", 2)


def test_weather_inverted_min_max_swapped(tmp_path):
    con, log = wx(tmp_path, [W("2026-01-01", "12.0", "20.0"), W("2026-01-02")])
    assert rows(con, "select temp_max_c, temp_min_c, temp_imputed, dq_flags from weather_daily order by date") == [
        (20.0, 12.0, False, "temp_swapped"), (20.0, 12.0, False, None)]
    assert _log_has(log, "weather_daily", "WX03", "fixed", 1)


def test_weather_null_precip_kept_and_flagged(tmp_path):
    con, log = wx(tmp_path, [W("2026-01-01", precip=""), W("2026-01-02", precip="0")])
    assert rows(con, "select precip_mm, dq_flags from weather_daily order by date") == [(None, "precip_missing"), (0.0, None)]
    assert _log_has(log, "weather_daily", "WX04", "flagged", 1)


def test_weather_flags_combine(tmp_path):
    con, _ = wx(tmp_path, [W("2026-01-01", "12.0", "20.0", ""), W("2026-01-02", "-999", "-999", ""), W("2026-01-03")])
    assert rows(con, "select dq_flags from weather_daily order by date") == [
        ("temp_swapped;precip_missing",), ("temp_imputed;precip_missing",), (None,)]


def test_validate_weather_coverage_detects_gaps(tmp_path):
    con, _ = wx(tmp_path, [W("2026-01-01")])
    res = validate.check_weather_coverage(con)
    assert res["ok"] is False and res["missing_site_days"] == 30


def test_validate_weather_coverage_passes_when_complete(tmp_path):
    con, _ = wx(tmp_path, [W(f"2026-01-{d:02d}") for d in range(1, 32)])
    assert validate.check_weather_coverage(con) == {"ok": True, "expected_site_days": 31, "missing_site_days": 0}


def test_weather_validation_keys():
    assert validate.PRIMARY_KEYS["weather_daily"] == ["site_id", "date"]
    assert ("weather_daily", "site_id", "sites", "site_id") in validate.FOREIGN_KEYS
