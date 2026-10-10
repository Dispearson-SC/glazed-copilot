import numpy as np
import pandas as pd


def synthetic_panel(n_days=84, seed=0, stores=("S1", "S2"), skus=("A", "B")):
    """Weekly-seasonal Poisson demand with the covariates the models expect."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-05", periods=n_days)  # starts on a Monday
    rows = []
    for st in stores:
        for sk in skus:
            base = 5 + 3 * (ord(sk[-1]) % 3)
            for d in dates:
                dow = d.dayofweek
                lam = base * (1.5 if dow >= 4 else 1.0)
                rows.append((st, sk, d, float(rng.poisson(lam)), False, False, dow))
    df = pd.DataFrame(rows, columns=["store_id", "sku", "date", "units", "censored", "inv_covered", "dow"])
    df["is_holiday"] = 0.0
    df["is_school_break"] = 0.0
    df["promo_pct"] = 0.0
    df["promo_bundle"] = 0.0
    df["site_type"] = "Airport"
    df["department"] = "Bakery"
    return df.sort_values(["store_id", "sku", "date"]).reset_index(drop=True)
