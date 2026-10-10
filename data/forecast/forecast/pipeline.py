"""End-to-end run: panel -> cutoff -> model selection -> calibration -> holdout forecast -> evaluation."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from forecast import calibration as cal
from forecast import data, evaluate as ev, metrics, models
from forecast import panel as P

QUANTILES = {"p10": 0.10, "p20": 0.20, "p50": 0.50, "p60": 0.60, "p74": 0.74, "p80": 0.80, "p85": 0.85, "p90": 0.90}
# scalar = same decay for levels and coefficients; (level, coef) = short-window levels with coefficients from a longer window
DEFAULT_HALF_LIVES = [None, 30, 14, 7, (30, None), (14, None), (7, None), (14, 90), (7, 90)]
COST_FALLBACK_RATIO = 0.4  # assumption: unit cost = 40% of price when the master has no cost


def _add_quantiles(fc: pd.DataFrame, bt: pd.DataFrame, center: bool = True):
    """Attach mu, quantiles, forecast(=p50), alpha per model using backtest calibration."""
    parts, grids, alphas, objs = [], [], [], {}
    for name, g in fc.groupby("model"):
        b = bt[bt["model"] == name]
        grid = cal.residual_grid(b["forecast"], b["actual"], center=center)
        atab = cal.nb_alpha_table(b["forecast"], b["actual"])
        g = g.rename(columns={"forecast": "mu"}).copy()
        for col, q in QUANTILES.items():
            g[col] = cal.quantile(g["mu"].to_numpy(), grid, q)
        g["alpha"] = cal.apply_alpha(g["mu"].to_numpy(), atab)
        g["forecast"] = g["p50"]
        parts.append(g)
        objs[name] = grid
        grids.append(grid.to_frame().assign(model=name))
        alphas.append(atab.assign(model=name))
    return pd.concat(parts, ignore_index=True), pd.concat(grids, ignore_index=True), pd.concat(alphas, ignore_index=True), objs


def leakage_check(panel: pd.DataFrame, cutoff, half_life, reference: pd.DataFrame) -> dict:
    """Re-run all models after corrupting every post-cutoff actual / censor flag; forecasts must not move."""
    train, _ = models.split_at_cutoff(panel, cutoff)
    pert = panel.copy()
    late = pert["date"] > pd.Timestamp(cutoff)
    pert.loc[late, "units"] = 123456.0
    pert.loc[late, "censored"] = True
    pert.loc[late, "inv_covered"] = True
    again = models.forecast_all(pert, cutoff, half_life=half_life)
    key = ["model", "store_id", "sku", "date"]
    a = reference[key + ["mu"]].sort_values(key).reset_index(drop=True)
    b = again.rename(columns={"forecast": "mu"}).sort_values(key).reset_index(drop=True)
    same = len(a) == len(b) and bool(np.allclose(a["mu"].to_numpy(), b["mu"].to_numpy(), rtol=0, atol=1e-9))
    return {
        "max_train_date": str(train["date"].max().date()),
        "train_max_le_cutoff": bool(train["date"].max() <= pd.Timestamp(cutoff)),
        "forecast_invariant_to_post_cutoff_actuals": same,
        "passed": bool(same and train["date"].max() <= pd.Timestamp(cutoff)),
    }


def _eval_frame(fc, panel, cutoff, scale, tables):
    act = panel[panel["date"] > cutoff][
        ["store_id", "sku", "date", "units", "censored", "inv_covered", "category", "format", "shelf_life_days",
         "is_perishable", "promo_pct", "promo_bundle", "dow", "unit_cost"]
    ].rename(columns={"units": "actual"})
    df = fc.merge(act, on=["store_id", "sku", "date"], how="left").merge(scale, on=["store_id", "sku"], how="left")
    df["shelf_class"] = P.shelf_life_class(df["shelf_life_days"], df["is_perishable"].fillna(False)).to_numpy()
    df["horizon_week"] = ((df["date"] - pd.Timestamp(cutoff)).dt.days - 1) // 7 + 1
    df["promo_window"] = np.where((df["promo_pct"] > 0) | (df["promo_bundle"] > 0), "promo", "no_promo")
    s = tables["sales_daily"]
    s = s[(pd.to_datetime(s["date"]) <= cutoff) & ~s["is_return"].astype(bool)]
    price = s.groupby("sku")["unit_price"].median().rename("price").reset_index()
    df = df.merge(price, on="sku", how="left")
    df["price"] = df["price"].fillna(df["price"].median())
    df["cost"] = df["unit_cost"].fillna(COST_FALLBACK_RATIO * df["price"])
    return df


def _business(df: pd.DataFrame) -> pd.DataFrame:
    policies = []
    for model, label in [("glm_poisson", "glm"), ("ma28_weekday", "ma28"), ("seasonal_naive", "snaive")]:
        g = df[df["model"] == model]
        policies.append((f"{label}_mean_no_buffer", model, g["mu"]))
        policies.append((f"{label}_p74", model, g["p74"]))
        if model == "glm_poisson":
            policies.append(("glm_p60", model, g["p60"]))
            policies.append(("glm_p85", model, g["p85"]))
    rows = []
    for name, model, S in policies:
        g = df[df["model"] == model].assign(S=S.to_numpy())
        rows.append({"policy": name, "model": model, **ev.simulate_policy(g)})
    return pd.DataFrame(rows)


FRONTIER_QS = [0.5, 0.55, 0.6, 0.65, 0.7, 0.74, 0.8, 0.85, 0.9, 0.95, 0.97, 0.99]
TARGET_FILL = 0.97


def _frontier(df: pd.DataFrame, grids) -> pd.DataFrame:
    """Sweep the order-up-to quantile for every model: service (fill rate) vs waste."""
    rows = []
    for model, g in df.groupby("model"):
        for q in FRONTIER_QS:
            S = cal.quantile(g["mu"].to_numpy(), grids[model], q)
            rows.append({"model": model, "q": q, **ev.simulate_policy(g.assign(S=S))})
    return pd.DataFrame(rows)


def run(clean_dir, out_dir, frac: float = 0.8, half_lives=None, center: bool = True) -> dict:
    half_lives = DEFAULT_HALF_LIVES if half_lives is None else half_lives
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tables = data.load_tables(clean_dir)
    panel, cutoff, last_day, first_day = data.build_model_panel(tables, frac)
    horizon = int((last_day - cutoff).days)
    train = panel[panel["date"] <= cutoff]

    best_hl, scores = cal.select_half_life(train, cutoff, half_lives, horizon)
    bt = cal.backtest(train, cutoff, horizon, half_life=best_hl)

    fc = models.forecast_all(panel, cutoff, half_life=best_hl)
    fc, grid, alpha, grid_objs = _add_quantiles(fc, bt, center)
    leak = leakage_check(panel, cutoff, best_hl, fc)

    scale = ev.series_scale(train)
    df = _eval_frame(fc, panel, cutoff, scale, tables)

    cols = ["model", "store_id", "sku", "date", "forecast", "mu", *QUANTILES, "alpha", "actual", "censored", "inv_covered"]
    df[cols].to_parquet(out / "forecast_holdout.parquet", index=False)

    ev_df = df.copy()
    ev_df["censored"] = ev_df["censored"].fillna(False).astype(bool)
    ev_df = ev_df.dropna(subset=["actual"])
    ev.group_summary(ev_df.assign(all="all"), "all").drop(columns="all").to_csv(out / "metrics_overall.csv", index=False)
    for name, col in [("store", "store_id"), ("category", "category"), ("shelf_class", "shelf_class"),
                      ("format", "format"), ("horizon_week", "horizon_week"), ("weekday", "dow"),
                      ("promo_window", "promo_window")]:
        ev.group_summary(ev_df, col).to_csv(out / f"metrics_by_{name}.csv", index=False)
    biz = _business(ev_df)
    biz.to_csv(out / "business_simulation.csv", index=False)
    front = _frontier(ev_df, grid_objs)
    front.to_csv(out / "business_frontier.csv", index=False)
    ev.at_fill_rate(front, TARGET_FILL).to_csv(out / "business_at_fill_97.csv", index=False)
    grid.to_csv(out / "calibration_grid.csv", index=False)
    alpha.to_csv(out / "nb_alpha_table.csv", index=False)

    forecastable = set(map(tuple, fc[["store_id", "sku"]].drop_duplicates().to_numpy()))
    hold = panel[panel["date"] > cutoff]
    in_scope = hold.apply(lambda r: (r["store_id"], r["sku"]) in forecastable, axis=1) if len(hold) else pd.Series(dtype=bool)
    g = hold.assign(in_scope=in_scope.to_numpy())
    meta = {
        "first_day": str(first_day.date()),
        "last_day": str(last_day.date()),
        "cutoff": str(cutoff.date()),
        "train_days": int((cutoff - first_day).days + 1),
        "holdout_days": horizon,
        "half_life": str(best_hl),
        "interval_centering": center,
        "half_life_backtest_wape": {str(k): v for k, v in scores.items()},
        "n_series_forecast": len(forecastable),
        "holdout_rows_total": int(len(g)),
        "holdout_rows_forecast": int(g["in_scope"].sum()),
        "holdout_units_total": float(g["units"].sum()),
        "holdout_units_not_forecast": float(g.loc[~g["in_scope"], "units"].sum()),
        "holdout_censored_share_inv_covered": float(g.loc[g["inv_covered"], "censored"].mean()),
        "leakage_check": leak,
    }
    (out / "run_meta.json").write_text(json.dumps(meta, indent=2, default=str))
    return meta
