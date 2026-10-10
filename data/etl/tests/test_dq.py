import duckdb
import pytest

from glazed_etl.dq import DQLog


def test_dq_log_records_and_writes_table():
    con = duckdb.connect()
    log = DQLog()
    log.add("sales_daily", "SD01", "dup rows", "excluded", 3, "kept first")
    con.execute("create table t as select 1 as x union all select 2")
    assert log.add_sql(con, "t", "T01", "x>1", "flagged", "select count(*) from t where x>1") == 1
    log.write(con)
    assert con.execute("select table_name, rule_id, treatment, affected_rows from dq_log order by 1").fetchall() == [
        ("sales_daily", "SD01", "excluded", 3),
        ("t", "T01", "flagged", 1),
    ]


def test_dq_log_rejects_unknown_treatment():
    with pytest.raises(ValueError):
        DQLog().add("t", "R", "i", "ignored", 1)
