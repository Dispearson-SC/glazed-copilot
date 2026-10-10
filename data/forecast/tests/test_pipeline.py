import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from forecast import pipeline
from forecast.__main__ import main

QCOLS = ["p10", "p20", "p50", "p60", "p74", "p80", "p85", "p90"]


def write_clean(tmp_path, n_days=150):
    rng = np.random.default_rng(3)
    dates = pd.date_range("2026-01-05", periods=n_days)
    stores = ["S1", "S2"]
    skus = ["A", "B", "C"]
    sales, inv = [], []
    for st in stores:
        for sk in skus:
            for d in dates:
                lam = (4 if sk != "C" else 2) * (1.4 if d.dayofweek >= 4 else 1.0)
                u = int(rng.poisson(lam))
                so = float(rng.random() < 0.1)
                if u > 0:
                    sales.append((d, st, sk, u, False, None, 2.5))
                if sk != "C":
                    inv.append((d, st, sk, u, 6.0 if so else 0.0))
    cal = []
    for st in stores:
        for d in dates:
            status = "open"
            if st == "S2" and d >= pd.Timestamp("2026-05-20"):
                status = "closed_permanently"
            cal.append((st, d, status))
    t = {
        "sales_daily": pd.DataFrame(sales, columns=["date", "store_id", "sku", "units_sold", "is_return", "promo_id", "unit_price"]),
        "inventory_daily": pd.DataFrame(inv, columns=["date", "store_id", "sku", "units_sold", "stockout_hours"]),
        "store_calendar": pd.DataFrame(cal, columns=["store_id", "date", "status"]),
        "calendar": pd.DataFrame(
            {"date": dates, "is_holiday": False, "is_school_break": False, "holiday_name": None}
        ),
        "products": pd.DataFrame(
            {
                "sku": skus,
                "department": ["Bakery", "Bakery", "Beverage"],
                "category": ["Bakery", "Bakery", "Coffee & Tea"],
                "shelf_life_days": [1, 3, np.nan],
                "is_perishable": [True, True, False],
                "unit_cost": [1.0, 1.0, 1.0],
            }
        ),
        "stores": pd.DataFrame({"store_id": stores, "site_id": ["ST1", "ST1"], "format": ["Full Counter", "Express Kiosk"]}),
        "sites": pd.DataFrame({"site_id": ["ST1"], "site_type": ["Airport"], "region": ["Northeast"]}),
        "promotions": pd.DataFrame(
            {
                "promo_id": ["P1"], "promo_type": ["Percent Off"], "start_date": [pd.Timestamp("2026-05-01")],
                "end_date": [pd.Timestamp("2026-05-10")], "discount_pct": [10.0], "department": ["Bakery"],
                "category": [None], "region_scope": ["ALL"],
            }
        ),
    }
    d = tmp_path / "clean"
    d.mkdir()
    con = duckdb.connect()
    for name, df in t.items():
        con.register("df", df)
        con.execute(f"copy df to '{d / (name + '.parquet')}' (format parquet)")
        con.unregister("df")
    return d


def test_run_end_to_end_contract(tmp_path):
    clean = write_clean(tmp_path)
    out = tmp_path / "out"
    res = pipeline.run(clean, out, half_lives=[None, 30])
    df = pd.read_parquet(out / "forecast_holdout.parquet")
    needed = {"store_id", "sku", "date", "forecast", "actual", "censored", "model", "mu", "alpha", *QCOLS}
    assert needed <= set(df.columns)
    assert set(df["model"]) == {"glm_poisson", "seasonal_naive", "ma28_weekday"}
    assert (df["forecast"] == df["p50"]).all()
    assert (df["p10"] <= df["p50"]).all() and (df["p50"] <= df["p90"]).all()
    assert (df["p74"] >= df["p50"]).all()
    # span 150 days from 2026-01-05 -> cutoff = 120th day
    assert res["cutoff"] == "2026-05-04"
    assert pd.to_datetime(df["date"]).min() > pd.Timestamp(res["cutoff"])


def test_closed_store_never_forecast(tmp_path):
    clean = write_clean(tmp_path)
    out = tmp_path / "out"
    pipeline.run(clean, out, half_lives=[None])
    df = pd.read_parquet(out / "forecast_holdout.parquet")
    s2 = df[df["store_id"] == "S2"]
    assert pd.to_datetime(s2["date"]).max() < pd.Timestamp("2026-05-20")


def test_cli_run_and_metrics_files(tmp_path):
    clean = write_clean(tmp_path)
    out = tmp_path / "out"
    rc = main(["run", "--clean", str(clean), "--out", str(out), "--half-lives", "none,30"])
    assert rc == 0
    meta = json.loads((out / "run_meta.json").read_text())
    assert meta["cutoff"] == "2026-05-04"
    assert meta["leakage_check"]["passed"] is True
    for f in ["metrics_overall.csv", "metrics_by_shelf_class.csv", "metrics_by_format.csv",
              "metrics_by_horizon_week.csv", "business_simulation.csv", "business_frontier.csv", "business_at_fill_97.csv", "calibration_grid.csv"]:
        assert (out / f).exists(), f
