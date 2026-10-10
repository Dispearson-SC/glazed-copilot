from datetime import date

import duckdb
import pytest

from glazed_backend.adapters.driven.forecast import BaselineForecast, FileForecast
from tests.fakes import make_series

D = date(2026, 3, 10)  # a Tuesday


def units(d):
    return 10 + d.isoweekday()  # weekday-dependent, flat across weeks


def hist(end=D, **kw):
    return [make_series("A", 2.0, date(2025, 12, 1), end, units, **kw)]


def test_baseline_is_the_same_weekday_average_of_the_previous_eight_weeks():
    res = BaselineForecast().forecast("S030", D, None, date(2026, 3, 11), date(2026, 3, 12), hist())
    assert res.model == "baseline-weekday-8w" and res.origin == D
    r = res.rows[0]
    assert (r.sku, r.date) == ("A", date(2026, 3, 11)) and r.forecast == pytest.approx(10 + 3)  # Wed
    assert r.quantiles["p10"] == r.quantiles["p90"] == pytest.approx(13)  # no spread in this series
    assert [x.date for x in res.rows] == [date(2026, 3, 11), date(2026, 3, 12)]


def test_baseline_spread_is_empirical():
    s = make_series("A", 2.0, date(2025, 12, 1), D, lambda d: 10 + (d.toordinal() // 7) % 4 * 2)
    r = BaselineForecast().forecast("S030", D, ["A"], date(2026, 3, 11), date(2026, 3, 11), [s]).rows[0]
    assert r.quantiles["p10"] < r.forecast < r.quantiles["p90"] and r.quantiles["p10"] < r.quantiles["p50"] < r.quantiles["p90"]


def test_baseline_origin_is_the_data_cutoff_when_it_is_before_as_of():
    res = BaselineForecast().forecast("S030", date(2026, 6, 1), None, date(2026, 3, 11), date(2026, 3, 11), hist())
    assert res.origin == D  # last data day <= as_of: min(as_of, cutoff)


def test_baseline_never_uses_rows_after_the_origin():
    leaky = [make_series("A", 2.0, date(2025, 12, 1), date(2026, 4, 30), lambda d: 10 if d <= D else 1000)]
    res = BaselineForecast().forecast("S030", D, None, date(2026, 3, 17), date(2026, 3, 17), leaky)
    assert res.origin == D and res.rows[0].forecast == pytest.approx(10)


def test_baseline_skips_dates_without_enough_history():
    s = make_series("A", 2.0, date(2026, 3, 8), D, units)
    assert BaselineForecast().forecast("S030", D, None, date(2026, 3, 11), date(2026, 3, 11), [s]).rows == []


def write_parquet(path, rows, cols):
    con = duckdb.connect()
    values = ", ".join("(" + ", ".join(repr(v) if isinstance(v, str) else str(v) for v in r) + ")" for r in rows)
    con.execute(f"CREATE TABLE t ({', '.join(cols)})")
    con.execute(f"INSERT INTO t VALUES {values}")
    con.execute(f"COPY t TO '{path}' (FORMAT parquet)")


BASE_COLS = ["store_id VARCHAR", "sku VARCHAR", "date DATE", "forecast DOUBLE", "p10 DOUBLE", "p90 DOUBLE",
             "actual DOUBLE", "censored BOOLEAN", "model VARCHAR"]


def test_file_forecast_reads_the_required_schema_and_filters(tmp_path):
    f = tmp_path / "f.parquet"
    write_parquet(f, [("S030", "A", "2026-07-20", 5.0, 3.0, 8.0, 4.0, False, "lgbm-1"),
                      ("S030", "B", "2026-07-20", 7.0, 5.0, 9.0, 7.0, False, "lgbm-1"),
                      ("S001", "A", "2026-07-20", 99.0, 90.0, 99.0, 1.0, False, "lgbm-1"),
                      ("S030", "A", "2026-07-30", 6.0, 3.0, 9.0, 4.0, False, "lgbm-1")], BASE_COLS)
    ff = FileForecast(str(f))
    res = ff.forecast("S030", date(2026, 7, 25), ["A"], date(2026, 7, 20), date(2026, 7, 25), [])
    assert res.model == "lgbm-1" and res.origin == date(2026, 7, 19)
    (r,) = res.rows
    assert r.sku == "A" and r.forecast == 5.0 and r.quantiles == {"p10": 3.0, "p90": 8.0}
    assert r.quantile(0.9) == 8.0 and r.quantile(0.74) == pytest.approx(5.0 + (0.24 / 0.4) * 3.0)  # p50..p90 interpolation


def test_file_forecast_uses_optional_quantile_columns_and_model_params_when_present(tmp_path):
    f = tmp_path / "f.parquet"
    write_parquet(f, [("S030", "A", "2026-07-20", 9.0, 3.0, 8.0, 4.0, False, "m", 4.5, 6.0, 7.0, 5.0, 0.3)],
                  BASE_COLS + ["p20 DOUBLE", "p50 DOUBLE", "p80 DOUBLE", "mu DOUBLE", "alpha DOUBLE"])
    (r,) = FileForecast(str(f)).forecast("S030", date(2026, 7, 25), None, date(2026, 7, 20), date(2026, 7, 20), []).rows
    assert r.forecast == 6.0  # p50 wins over the generic forecast column
    assert r.quantiles == {"p10": 3.0, "p20": 4.5, "p50": 6.0, "p80": 7.0, "p90": 8.0} and r.extra == {"mu": 5.0, "alpha": 0.3}
    assert r.quantile(0.74) == pytest.approx(6.0 + (0.24 / 0.3) * 1.0)


def test_file_forecast_quantile_method_and_a_missing_or_unreadable_file(tmp_path):
    f = tmp_path / "f.parquet"
    write_parquet(f, [("S030", "A", "2026-07-20", 5.0, 3.0, 8.0, 4.0, False, "m")], BASE_COLS)
    ff = FileForecast(str(f))
    assert ff.quantile("S030", date(2026, 7, 25), "A", date(2026, 7, 20), 0.5, []) == 5.0
    assert ff.quantile("S030", date(2026, 7, 25), "ZZ", date(2026, 7, 20), 0.5, []) is None
    assert FileForecast(str(tmp_path / "nope.parquet")).forecast("S030", D, None, D, D, []) is None


def test_file_forecast_origin_is_configurable(tmp_path):
    f = tmp_path / "f.parquet"
    write_parquet(f, [("S030", "A", "2026-07-20", 5.0, 3.0, 8.0, 4.0, False, "m")], BASE_COLS)
    res = FileForecast(str(f), origin=date(2026, 7, 1)).forecast("S030", date(2026, 7, 25), None, date(2026, 7, 20), date(2026, 7, 20), [])
    assert res.origin == date(2026, 7, 1)


def test_baseline_quantile_method():
    assert BaselineForecast().quantile("S030", D, "A", date(2026, 3, 11), 0.5, hist()) == pytest.approx(13)


def test_file_forecast_accepts_a_timestamp_date_column(tmp_path):
    """The holdout job writes `date` as TIMESTAMP; rows must still compare with `date`."""
    f = tmp_path / "f.parquet"
    cols = [c.replace("date DATE", "date TIMESTAMP") for c in BASE_COLS]
    write_parquet(f, [("S030", "A", "2026-07-20 00:00:00", 5.0, 3.0, 8.0, 4.0, False, "glm-1")], cols)
    res = FileForecast(str(f)).forecast("S030", date(2026, 7, 25), ["A"], date(2026, 7, 20), date(2026, 7, 25), [])
    (r,) = res.rows
    assert r.date == date(2026, 7, 20) and type(r.date) is date
