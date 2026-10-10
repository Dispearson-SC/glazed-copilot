from datetime import date

from glazed_backend.adapters.driven.forecast import BaselineForecast, FileForecast
from glazed_backend.adapters.driving.app import build_forecasters


def test_file_forecast_comes_first_only_when_the_path_exists(tmp_path):
    f = tmp_path / "f.parquet"
    f.write_bytes(b"x")
    chain = build_forecasters({"GLAZED_FORECAST_PATH": str(f)})
    assert [type(x) for x in chain] == [FileForecast, BaselineForecast]
    for env in ({}, {"GLAZED_FORECAST_PATH": ""}, {"GLAZED_FORECAST_PATH": str(tmp_path / "missing.parquet")}):
        assert [type(x) for x in build_forecasters(env)] == [BaselineForecast]


def test_the_holdout_origin_is_configurable(tmp_path):
    f = tmp_path / "f.parquet"
    f.write_bytes(b"x")
    ff = build_forecasters({"GLAZED_FORECAST_PATH": str(f), "GLAZED_FORECAST_ORIGIN": "2026-07-01"})[0]
    assert ff.origin == date(2026, 7, 1)
    assert build_forecasters({"GLAZED_FORECAST_PATH": str(f)})[0].origin == date(2026, 7, 19)
