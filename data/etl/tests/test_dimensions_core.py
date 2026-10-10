from datetime import date

from glazed_etl import dimensions as dim
from glazed_etl.dq import DQLog
from tests.helpers import make_con, rows


def _log_has(log, table, rule, treatment, n):
    return any(e[:2] == (table, rule) and e[3] == treatment and e[4] == n for e in log.entries)


# ---------------------------------------------------------------- sites / suppliers
def test_sites_typed_and_deduplicated(tmp_path):
    con = make_con(tmp_path, sites=[
        {"site_id": "ST01", "site_name": " Harbor Airport ", "site_type": "Airport", "region": "Northeast", "traffic_tier": "1.6"},
        {"site_id": "ST01", "site_name": "Harbor Airport", "site_type": "Airport", "region": "Northeast", "traffic_tier": "1.6"},
        {"site_id": "ST02", "site_name": "Rail", "site_type": "Rail Station", "region": "Mountain", "traffic_tier": ""},
    ])
    log = DQLog()
    dim.build_sites(con, log)
    assert rows(con, "select site_id, site_name, traffic_tier from sites order by 1") == [
        ("ST01", "Harbor Airport", 1.6), ("ST02", "Rail", None)]
    assert _log_has(log, "sites", "SI01", "excluded", 1)


def test_suppliers_typed(tmp_path):
    con = make_con(tmp_path, suppliers=[
        {"supplier_id": "SUP01", "supplier_name": "Northfield", "category_focus": "Bakery",
         "standard_lead_time_days": "1", "contract_fill_rate": "0.95", "contract_on_time_rate": "0.93",
         "min_order_value": "150", "delivery_days": "Daily"}])
    dim.build_suppliers(con, DQLog())
    assert rows(con, "select supplier_id, standard_lead_time_days, contract_fill_rate from suppliers") == [("SUP01", 1, 0.95)]


# ---------------------------------------------------------------- calendar
def test_calendar_recomputes_quarter_and_checks_derived_columns(tmp_path):
    con = make_con(tmp_path, calendar=[
        {"date": "2025-12-31", "day_of_week": "Wed", "iso_week": "1", "month": "12", "year": "2025",
         "quarter_idx": "0", "is_weekend": "0", "is_holiday": "1", "holiday_name": "New Year's Eve", "is_school_break": "1"},
        {"date": "2026-04-05", "day_of_week": "Sun", "iso_week": "14", "month": "4", "year": "2026",
         "quarter_idx": "1", "is_weekend": "1", "is_holiday": "1", "holiday_name": "Easter", "is_school_break": "0"},
    ])
    log = DQLog()
    dim.build_calendar(con, log)
    assert rows(con, "select date, quarter, is_weekend, is_holiday, holiday_name from calendar order by date") == [
        (date(2025, 12, 31), 4, False, True, "New Year's Eve"),
        (date(2026, 4, 5), 2, True, True, "Easter"),
    ]
    # raw quarter_idx 0 != 3 and 1 == 1 (0-based calendar quarter) -> exactly 1 row fixed
    assert _log_has(log, "calendar", "CA01", "fixed", 1)


# ---------------------------------------------------------------- stores
STORE_BASE = {"format": "Full Counter", "operator_type": "Owned F&B", "opened_date": "2020-01-01", "sqft": "100", "seats": "5"}


def _stores(tmp_path, extra_kpis=(), closures=(), s002_closed=""):
    stores = [
        {**STORE_BASE, "store_id": "S001", "site_id": "ST01", "store_name": "food court – full counter 1",
         "opening_time": "03:00", "closing_time": "21:00"},
        {**STORE_BASE, "store_id": "S002", "site_id": "ST01", "store_name": "Terminal C – Shop-in-Shop 4  ",
         "opening_time": "00:00", "closing_time": "00:00", "opened_date": "2024-08-02", "sqft": "120", "closed_date": s002_closed},
        {**STORE_BASE, "store_id": "S003", "site_id": "ST02", "store_name": "Gate", "opening_time": "#N/A", "closing_time": "21:00"},
        {**STORE_BASE, "store_id": "S004", "site_id": "ST02", "store_name": "Gate 2", "opening_time": "", "closing_time": "23:00"},
        {**STORE_BASE, "store_id": "S005", "site_id": "ST01", "store_name": "TERMINAL C – SHOP-IN-SHOP 4",
         "opening_time": "00:00", "closing_time": "00:00", "opened_date": "2024-08-02", "sqft": "120"},
        {**STORE_BASE, "store_id": "S006", "site_id": "ST99", "store_name": "Unknown Kiosk", "opening_time": "05:00", "closing_time": "21:00"},
    ]
    sites = [{"site_id": "ST01"}, {"site_id": "ST02"}]
    kpis = [{"store_id": "S003", "date": "2025-10-01", "open_hours": "18"},
            {"store_id": "S003", "date": "2025-10-02", "open_hours": "18"}, *extra_kpis]
    con = make_con(tmp_path, stores=stores, sites=sites, store_daily_kpis=kpis, store_closures=list(closures))
    log = DQLog()
    dim.build_sites(con, log)
    dim.build_stores(con, log)
    return con, log


def test_stores_clean_names_and_ids(tmp_path):
    con, _ = _stores(tmp_path)
    got = dict(rows(con, "select store_id, store_name from stores"))
    assert got["S001"] == "Food Court – Full Counter 1"
    assert got["S002"] == "Terminal C – Shop-in-Shop 4"


def test_stores_duplicate_merged_into_lowest_id_and_mapped(tmp_path):
    con, log = _stores(tmp_path)
    assert "S005" not in [r[0] for r in rows(con, "select store_id from stores")]
    assert rows(con, "select old_store_id, store_id from store_id_map where old_store_id='S005'") == [("S005", "S002")]
    assert _log_has(log, "stores", "ST01", "excluded", 1)


def test_stores_orphan_site_excluded(tmp_path):
    con, log = _stores(tmp_path)
    assert "S006" not in [r[0] for r in rows(con, "select store_id from stores")]
    assert _log_has(log, "stores", "ST02", "excluded", 1)


def test_stores_missing_opening_time_inferred_from_open_hours(tmp_path):
    con, log = _stores(tmp_path)
    got = dict(rows(con, "select store_id, opening_time from stores"))
    assert got["S003"] == "03:00"  # 21:00 - 18h
    assert got["S004"] is None  # no KPI evidence -> stays unknown
    flags = dict(rows(con, "select store_id, dq_flags from stores"))
    assert "opening_time_inferred" in flags["S003"]
    assert "opening_time_unknown" in flags["S004"]
    assert _log_has(log, "stores", "ST04", "fixed", 1)
    assert _log_has(log, "stores", "ST05", "flagged", 1)


def test_stores_name_fixes_logged(tmp_path):
    _, log = _stores(tmp_path)
    # S001 (all lower), S002 (trailing spaces), S005 (all upper; excluded dup still counted by raw rule)
    assert any(e[:2] == ("stores", "ST03") and e[4] >= 2 for e in log.entries)


# ---------------------------------------------------------------- closures + store calendar
def test_closures_and_store_calendar(tmp_path):
    closures = [
        {"store_id": "S001", "start_date": "2025-11-16", "end_date": "2025-11-17", "reason": "Equipment failure"},
        {"store_id": "S002", "start_date": "2026-07-13", "end_date": "2026-07-13", "reason": "Permanent closure"},
        {"store_id": "S077", "start_date": "2025-11-16", "end_date": "2025-11-17", "reason": "x"},
        {"store_id": "s005", "start_date": "2025-12-01", "end_date": "2025-12-02", "reason": "Renovation"},
    ]
    con, log = _stores(tmp_path, closures=closures, s002_closed="2026-07-13")
    dim.build_store_closures(con, log)
    assert rows(con, "select store_id, is_permanent from store_closures order by store_id, start_date") == [
        ("S001", False), ("S002", False), ("S002", True)]  # S005 remapped to S002
    assert _log_has(log, "store_closures", "SC01", "excluded", 1)
    con.execute("create or replace table calendar as select unnest(generate_series(date '2025-11-15', date '2026-07-14', interval 1 day))::date as date")
    dim.build_store_calendar(con, log)
    st = lambda s, d: rows(con, f"select status from store_calendar where store_id='{s}' and date='{d}'")[0][0]
    assert st("S001", "2025-11-15") == "open"
    assert st("S001", "2025-11-16") == "temporary_closure"
    assert st("S001", "2025-11-18") == "open"
    assert st("S002", "2025-12-01") == "temporary_closure"
    assert st("S002", "2026-07-12") == "open"
    assert st("S002", "2026-07-13") == "closed_permanently"
