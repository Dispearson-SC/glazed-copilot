from datetime import date

import pytest

from glazed_etl import normalize as n


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-08-02", date(2026, 8, 2)),
        ("01-Aug-26", date(2026, 8, 1)),
        ("05-oct-25", date(2025, 10, 5)),
        ("01/31/2026", date(2026, 1, 31)),  # MM/DD/YYYY
        ("12/01/2025", date(2025, 12, 1)),  # ambiguous -> MM/DD by assumption
        (" 2026-08-02 ", date(2026, 8, 2)),
        ("", None),
        (None, None),
        ("not a date", None),
        ("2026-02-30", None),
    ],
)
def test_parse_date(raw, expected):
    assert n.parse_date(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("S001", "S001"),
        ("s001", "S001"),
        ("S001 ", "S001"),
        ("S0001", "S001"),
        ("S99", "S099"),
        ("S120", "S120"),
        ("", None),
        (None, None),
        ("XYZ", None),
    ],
)
def test_normalize_store_id(raw, expected):
    assert n.normalize_store_id(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("SKU-100003", "SKU-100003"),
        ("sku-100003", "SKU-100003"),
        ("SKU100003", "SKU-100003"),
        (" SKU-100003 ", "SKU-100003"),
        ("SKU-100003 ", "SKU-100003"),
        ("", None),
        (None, None),
        ("ABC", None),
    ],
)
def test_normalize_sku(raw, expected):
    assert n.normalize_sku(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("USD", "USD"),
        ("Usd", "USD"),
        ("usd", "USD"),
        ("US$", "USD"),
        ("USD ", "USD"),
        ("EUR", None),
        (None, None),
    ],
)
def test_normalize_currency(raw, expected):
    assert n.normalize_currency(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  food court  –  full counter 1 ", "Food Court – Full Counter 1"),
        ("ARRIVALS HALL", "Arrivals Hall"),
        ("Arrivals hall", "Arrivals hall"),  # mixed case is left alone
        ("Shop-in-Shop 2", "Shop-in-Shop 2"),
        ("DEPARTURES LOBBY – SHOP-IN-SHOP 4", "Departures Lobby – Shop-in-Shop 4"),
        ("  Terminal C – Full Counter 3   ", "Terminal C – Full Counter 3"),
        ("", None),
        (None, None),
    ],
)
def test_clean_name(raw, expected):
    assert n.clean_name(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [("12", 12.0), (" 3.5 ", 3.5), ("", None), (None, None), ("#N/A", None), ("abc", None)],
)
def test_to_float(raw, expected):
    assert n.to_float(raw) == expected


def test_parse_time():
    assert n.parse_time("03:00") == "03:00"
    assert n.parse_time("3:00") == "03:00"
    assert n.parse_time("#N/A") is None
    assert n.parse_time("") is None
    assert n.parse_time(None) is None


def test_sql_normalizers_use_distinct_value_maps():
    import duckdb

    con = duckdb.connect()
    n.register_normalizers(con)
    n.populate(con, "store", ["s001 ", "S001", "bad", None])
    n.populate(con, "sku", ["sku100003"])
    n.populate(con, "date", ["01/31/2026"])
    n.populate(con, "currency", ["US$"])
    n.populate(con, "float", ["#N/A"])
    n.populate(con, "store", ["s001 "])  # idempotent
    row = con.execute(
        "select norm_store('s001 '), norm_store('bad'), norm_sku('sku100003'), "
        "norm_date('01/31/2026'), norm_currency('US$'), norm_float('#N/A'), norm_sku(NULL)"
    ).fetchone()
    assert row == ("S001", None, "SKU-100003", date(2026, 1, 31), "USD", None, None)
    assert con.execute("select count(*) from nm_store").fetchone()[0] == 3
