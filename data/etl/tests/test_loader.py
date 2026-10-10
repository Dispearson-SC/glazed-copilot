import pytest

from glazed_etl import loader
from tests.helpers import make_con, make_raw, rows


def test_load_raw_keeps_everything_as_text_in_file_order(tmp_path):
    con = make_con(
        tmp_path,
        sales_daily=[
            {"date": "01/31/2026", "store_id": "s001 ", "sku": "sku100003", "units_sold": "x"},
            {"date": "2026-01-02", "store_id": "S001", "sku": "SKU-100003", "units_sold": "5"},
        ],
    )
    out = rows(con, "select _rn, date, store_id, units_sold, promo_id from raw.sales_daily order by _rn")
    assert out == [(1, "01/31/2026", "s001 ", "x", None), (2, "2026-01-02", "S001", "5", None)]


def test_load_raw_populates_normalizer_maps(tmp_path):
    con = make_con(
        tmp_path,
        sales_daily=[{"date": "01/31/2026", "store_id": "s001 ", "sku": "sku100003"}],
        prices=[{"currency": "US$", "effective_from": "03/01/2026"}],
    )
    assert rows(con, "select norm_store('s001 '), norm_sku('sku100003'), norm_currency('US$')") == [
        ("S001", "SKU-100003", "USD")
    ]
    assert rows(con, "select norm_date('03/01/2026')")[0][0].isoformat() == "2026-03-01"


def test_load_raw_fails_clearly_when_file_missing(tmp_path):
    import duckdb

    raw = make_raw(tmp_path)
    (raw / "sites.csv").unlink()
    with pytest.raises(FileNotFoundError, match="sites.csv"):
        loader.load_raw(duckdb.connect(), raw)
