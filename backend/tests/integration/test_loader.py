import os

import duckdb
import pytest

URL = os.environ.get("GLAZED_TEST_DATABASE_URL", "postgresql://glazed_app:glazed_dev@localhost:55432/glazed_test")
pytestmark = pytest.mark.integration


def _conn():
    psycopg = pytest.importorskip("psycopg")
    try:
        return psycopg.connect(URL, connect_timeout=2, autocommit=True)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres not reachable: {exc}")


def test_loader_is_idempotent_and_types_survive(tmp_path):
    from glazed_backend.loader import load_parquet_dir
    con = duckdb.connect()
    con.execute(f"COPY (SELECT 'S1' AS store_id, DATE '2026-03-01' AS date, 3 AS qty, 1.5 AS price, true AS ok"
                f" UNION ALL SELECT 'S2', DATE '2026-03-02', NULL, 2.5, false) TO '{tmp_path}/t_unit.parquet' (FORMAT parquet)")
    c = _conn()
    c.execute("DROP TABLE IF EXISTS glazed.ds_t_unit")
    first = load_parquet_dir(str(tmp_path), URL)
    second = load_parquet_dir(str(tmp_path), URL)
    assert first == second == {"t_unit": 2}
    rows = c.execute("SELECT store_id, date, qty, price, ok FROM glazed.ds_t_unit ORDER BY store_id").fetchall()
    assert rows[0][1].isoformat() == "2026-03-01" and rows[1][2] is None and rows[0][4] is True
    c.execute("DROP TABLE glazed.ds_t_unit")
