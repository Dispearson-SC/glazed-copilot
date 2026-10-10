import json
import os
import subprocess
import sys
from pathlib import Path

import duckdb

from glazed_etl import pipeline, validate

FIXTURE = Path(__file__).parent / "fixtures" / "raw_min"
ROOT = Path(__file__).resolve().parent.parent


def test_pipeline_writes_all_outputs(tmp_path):
    out = tmp_path / "clean"
    result = pipeline.run(FIXTURE, out)
    for name in ("sales_daily", "stores", "products", "prices", "dq_log", "store_daily_kpis"):
        assert (out / f"{name}.parquet").is_file(), name
    assert (out / "dq_log.csv").is_file() and (out / "validation.json").is_file() and (out / "glazed.duckdb").is_file()
    assert json.loads((out / "validation.json").read_text())["checks"]["primary_keys"]["ok"] is True
    con = duckdb.connect(str(out / "glazed.duckdb"), read_only=True)
    assert con.execute("select count(*) from sales_daily").fetchone()[0] == 4  # exact duplicate and orphan SKU removed
    assert con.execute("select count(*) from v_sales_enriched").fetchone()[0] == 4
    assert con.execute("select count(*) from v_store_day").fetchone()[0] == 2
    assert con.execute("select count(*) from weather_daily").fetchone()[0] == 31  # duplicate removed
    assert con.execute("select count(*) from v_store_day_weather").fetchone()[0] == 31  # 1 store at ST01
    assert con.execute("select temp_max_c, temp_imputed from weather_daily where date = '2026-01-05'").fetchone() == (10.0, True)
    assert result["validation"]["checks"]["weather_coverage"]["ok"] is True
    assert con.execute("select count(*) from information_schema.schemata where schema_name = 'raw'").fetchone()[0] == 0
    assert result["row_counts"]["sales_daily"] == {"raw": 6, "clean": 4}


def test_pipeline_is_idempotent(tmp_path):
    out = tmp_path / "clean"
    first = pipeline.run(FIXTURE, out)
    csv1 = (out / "dq_log.csv").read_text()
    second = pipeline.run(FIXTURE, out)
    assert first["row_counts"] == second["row_counts"]
    assert csv1 == (out / "dq_log.csv").read_text()


def test_raw_inputs_are_never_modified(tmp_path):
    before = {p.name: p.read_bytes() for p in FIXTURE.glob("*.csv")}
    pipeline.run(FIXTURE, tmp_path / "clean")
    assert before == {p.name: p.read_bytes() for p in FIXTURE.glob("*.csv")}


def test_validation_reports_sales_vs_kpi(tmp_path):
    result = pipeline.run(FIXTURE, tmp_path / "clean")
    chk = result["validation"]["checks"]["sales_vs_kpi"]
    assert chk["store_days_compared"] == 2
    assert chk["within_1pct"] == 2  # 14.00 and 12.00 match the cleaned sales
    assert chk["ok"] is True
    assert result["validation"]["checks"]["foreign_keys"]["ok"] is True


def test_cli_runs_and_prints_summary(tmp_path):
    out = tmp_path / "clean"
    proc = subprocess.run([sys.executable, "-m", "glazed_etl", "--raw", str(FIXTURE), "--out", str(out)],
                          cwd=ROOT, capture_output=True, text=True, env={"PYTHONPATH": os.pathsep.join([str(ROOT), *[p for p in sys.path if p]]), "PATH": ""})
    assert proc.returncode == 0, proc.stderr
    assert "sales_daily" in proc.stdout and "validation" in proc.stdout.lower()


def test_validate_flags_broken_keys():
    con = duckdb.connect()
    con.execute("create table stores as select 'S1' as store_id union all select 'S1'")
    res = validate.check_primary_keys(con, {"stores": ["store_id"]})
    assert res["ok"] is False and res["duplicates"]["stores"] == 1
