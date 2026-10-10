"""Build the store x SKU x day modelling panel from the cleaned tables.

Rules enforced here:
* only days on which the store was trading (store_calendar.status == 'open') exist in the panel;
* demand = units sold excluding returns, zero-filled on open days from the first day the
  series is observed (sales or inventory row);
* a day is *censored* when inventory reports stockout hours > 0 (sales understate demand).
  SKUs outside inventory_daily are never flagged (``inv_covered`` = False).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

KEY = ["store_id", "sku", "date"]


def shared_span(spans):
    """Intersection of (min, max) date spans."""
    lo = max(s[0] for s in spans)
    hi = min(s[1] for s in spans)
    return pd.Timestamp(lo), pd.Timestamp(hi)


def compute_cutoff(lo, hi, frac: float = 0.8) -> pd.Timestamp:
    """Last training day: the first ceil(frac * n_days) days of [lo, hi] are training."""
    lo, hi = pd.Timestamp(lo), pd.Timestamp(hi)
    n = (hi - lo).days + 1
    n_train = int(np.ceil(round(frac * n, 9)))
    return lo + pd.Timedelta(days=n_train - 1)


def build_panel(sales: pd.DataFrame, inventory: pd.DataFrame, store_calendar: pd.DataFrame) -> pd.DataFrame:
    sales = sales.copy()
    sales["date"] = pd.to_datetime(sales["date"])
    inventory = inventory.copy()
    inventory["date"] = pd.to_datetime(inventory["date"])
    cal = store_calendar.copy()
    cal["date"] = pd.to_datetime(cal["date"])
    open_days = cal.loc[cal["status"] == "open", ["store_id", "date"]]

    demand = sales.loc[~sales["is_return"].astype(bool) & (sales["units_sold"] > 0)]
    demand = demand.groupby(KEY, as_index=False)["units_sold"].sum().rename(columns={"units_sold": "units"})

    inv = inventory.groupby(KEY, as_index=False).agg(stockout_hours=("stockout_hours", "max"))

    firsts = pd.concat(
        [sales[KEY].groupby(["store_id", "sku"])["date"].min(), inv[KEY].groupby(["store_id", "sku"])["date"].min()],
        axis=1,
    ).min(axis=1)
    firsts = firsts.rename("first_seen").reset_index()

    panel = firsts.merge(open_days, on="store_id")
    panel = panel[panel["date"] >= panel["first_seen"]].drop(columns="first_seen")
    panel = panel.merge(demand, on=KEY, how="left").merge(inv, on=KEY, how="left")
    panel["units"] = panel["units"].fillna(0.0)
    panel["inv_covered"] = panel["stockout_hours"].notna()
    panel["censored"] = panel["stockout_hours"].fillna(0) > 0
    panel = panel.drop(columns="stockout_hours")
    return panel.sort_values(KEY).reset_index(drop=True)


def add_promo_features(panel: pd.DataFrame, promos: pd.DataFrame) -> pd.DataFrame:
    """Planned-promotion covariates (known in advance, so legitimate for the holdout).

    promo_pct    = discount fraction when an active 'Percent Off' promo covers the row
    promo_bundle = 1 when an active 'Bundle' promo covers the row
    """
    out = panel.copy()
    out["promo_pct"] = 0.0
    out["promo_bundle"] = 0.0
    for r in promos.itertuples(index=False):
        m = (out["date"] >= pd.Timestamp(r.start_date)) & (out["date"] <= pd.Timestamp(r.end_date))
        if pd.notna(r.department):
            m &= out["department"] == r.department
        if pd.notna(r.category):
            m &= out["category"] == r.category
        if pd.notna(r.region_scope) and str(r.region_scope).upper() != "ALL":
            m &= out["region"] == r.region_scope
        if str(r.promo_type).lower().startswith("bundle"):
            out.loc[m, "promo_bundle"] = 1.0
        else:
            out.loc[m, "promo_pct"] = np.maximum(out.loc[m, "promo_pct"], float(r.discount_pct) / 100.0)
    return out


def add_static_features(panel, calendar, products, stores, sites, promos) -> pd.DataFrame:
    """Join calendar, product, store/site attributes and planned promotions."""
    cal = calendar.copy()
    cal["date"] = pd.to_datetime(cal["date"])
    cal["dow"] = cal["date"].dt.dayofweek
    cal = cal[["date", "dow", "is_holiday", "is_school_break", "holiday_name"]]
    prod = products[["sku", "department", "category", "shelf_life_days", "is_perishable", "unit_cost"]]
    st = stores[["store_id", "site_id", "format"]].merge(sites[["site_id", "site_type", "region"]], on="site_id")
    out = panel.merge(cal, on="date", how="left").merge(prod, on="sku", how="left").merge(st, on="store_id", how="left")
    out["is_holiday"] = out["is_holiday"].astype(float)
    out["is_school_break"] = out["is_school_break"].astype(float)
    return add_promo_features(out, promos)


def shelf_life_class(days, perishable) -> pd.Series:
    """1d / 2-3d / 4-5d for perishables; everything else (incl. unknown life) is non-perishable."""
    d = pd.Series(days, dtype="float").reset_index(drop=True)
    per = pd.Series(perishable, dtype="bool").reset_index(drop=True)
    out = pd.Series("non-perishable", index=d.index, dtype=object)
    out[per & (d <= 1)] = "1d"
    out[per & (d > 1) & (d <= 3)] = "2-3d"
    out[per & (d > 3)] = "4-5d"
    return out
