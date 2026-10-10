"""Alert 9: unknown products. Two distinct findings on the raw sales layer (the clean tables no longer hold them):
a SKU key written in another format that matches the master once normalised, and real orphans. No I/O."""
from __future__ import annotations

import re
from datetime import date

from .issues import _issue
from .options import make_option
from .types import Config

SOURCE = "raw sales_daily vs raw products (glazed_raw audit layer)"


def normalize_sku(sku: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", sku.upper())


def scan_sales(sales: list[tuple], master: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """sales rows: (store_id, sku, rows, net_sales, days). master: sku -> product name.
    Returns (key mismatches, orphans), each aggregated by raw SKU."""
    by_norm = {normalize_sku(k): k for k in master}
    agg: dict[str, dict] = {}
    for store, sku, rows, net, days in sales:
        if sku in master:
            continue
        a = agg.setdefault(sku, {"sku": sku, "rows": 0, "net_sales": 0.0, "days": 0, "by_store": {}})
        a["rows"] += rows
        a["net_sales"] = round(a["net_sales"] + net, 2)
        a["days"] = max(a["days"], days)
        a["by_store"][store] = round(a["by_store"].get(store, 0.0) + net, 2)
    mism, orphans = [], []
    for sku, a in sorted(agg.items()):
        key = by_norm.get(normalize_sku(sku))
        if key:
            mism.append({**a, "master_sku": key, "product_name": master[key]})
        else:
            orphans.append(a)
    return mism, orphans


def _fix_option(iid: str, params: dict, why: str, risk: list[str], deadline: str) -> dict:
    ev = {"benefit": {"low": 0.0, "mid": 0.0, "high": 0.0}, "cost_usd": 0.0, "net_mid": 0.0, "waste_delta": 0.0, "lost_delta": 0.0}
    o = make_option(iid, "data_fix_task", params, ev, {"deadline_date": deadline, "reason": why}, risk)
    o["confidence"] = {"score": 1.0, "n_backtest": 0, "method": "rule", "noise_capped": False,
                       "effect_mean_usd": None, "noise_floor_usd": None}
    o["tier"], o["tier_reasons"] = "N2", ["data task: a person corrects the master or reports to corporate (never automatic)"]
    return o


def _nothing(iid: str, exposure: float, why: str) -> dict:
    ev = {"benefit": {"low": 0.0, "mid": 0.0, "high": 0.0}, "cost_usd": 0.0, "net_mid": 0.0, "waste_delta": 0.0, "lost_delta": 0.0}
    o = make_option(iid, "do_nothing", {}, ev, {"deadline_date": None, "reason": why}, [],
                    cost_of_inaction_usd={"mid": 0.0})
    o["confidence"] = {"score": 1.0, "n_backtest": 0, "method": "baseline", "noise_capped": False,
                       "effect_mean_usd": None, "noise_floor_usd": None}
    o["tier"], o["tier_reasons"] = "N0", [f"do_nothing leaves ${exposure:,.0f} of sales without cost or category"]
    return o


MATERIAL_USD = 10_000.0  # smaller key variants (the master has ~1,000 formatting variants) are summarised, not alerted


def integrity_issues(store_id: str, as_of: date, ref: date, mismatches: list[dict], orphans: list[dict],
                     cfg: Config, min_usd: float = MATERIAL_USD) -> list[dict]:
    """Integrity tasks (tier N2). severity_usd is 0: the amounts are sales exposure, not a loss, so they must not
    crowd operational alerts; `exposure_usd` carries the sales at stake."""
    out = []
    day = as_of.isoformat()
    minor = [m for m in mismatches if m["net_sales"] < min_usd]
    for m in mismatches:
        if m["net_sales"] < min_usd:
            continue
        iid = f"{store_id}|sku_key_mismatch|{m['sku']}"
        mine = m["by_store"].get(store_id, 0.0)
        ev = [{"metric": "recoverable_sales_chain_usd", "value": m["net_sales"], "unit": "USD", "period": f"through {day}", "source": SOURCE},
              {"metric": "recoverable_sales_store_usd", "value": mine, "unit": "USD", "period": f"through {day}", "source": SOURCE},
              {"metric": "rows", "value": m["rows"], "unit": "rows", "period": f"through {day}", "source": SOURCE},
              {"metric": "raw_key", "value": m["sku"], "unit": "text", "period": "raw", "source": SOURCE},
              {"metric": "master_key", "value": m["master_sku"], "unit": "text", "period": "raw", "source": SOURCE},
              {"metric": "other_mismatched_keys", "value": len(minor), "unit": "keys", "period": f"through {day}",
               "source": f"{SOURCE}; ${sum(x['net_sales'] for x in minor):,.0f} in total, each under ${min_usd:,.0f}"}]
        opts = [_fix_option(iid, {"raw_sku": m["sku"], "master_sku": m["master_sku"], "product_name": m["product_name"]},
                            f"Correct the key so {m['sku']} matches {m['master_sku']}.",
                            ["Sales without the right key have no cost, category or reorder."], day),
                _nothing(iid, m["net_sales"], "The sales stay outside cost, category and reorder.")]
        out.append(_issue(store_id, "sku_key_mismatch", m["sku"], as_of, ref, 0.0, ev,
                          [f"{m['sku']} is not a new product: it is {m['master_sku']} ({m['product_name']}) written in another format."],
                          opts, opts[0]["option_id"], sku=m["sku"], product_name=m["product_name"], category="integrity",
                          integrity=True, exposure_usd=m["net_sales"]))
    if orphans:
        total = round(sum(o["net_sales"] for o in orphans), 2)
        rows = sum(o["rows"] for o in orphans)
        mine = round(sum(o["by_store"].get(store_id, 0.0) for o in orphans), 2)
        iid = f"{store_id}|orphan_sku|SKU-7xxxxx"
        ev = [{"metric": "orphan_sales_chain_usd", "value": total, "unit": "USD", "period": f"through {day}", "source": SOURCE},
              {"metric": "orphan_sales_store_usd", "value": mine, "unit": "USD", "period": f"through {day}", "source": SOURCE},
              {"metric": "orphan_rows", "value": rows, "unit": "rows", "period": f"through {day}", "source": SOURCE},
              {"metric": "orphan_skus", "value": len(orphans), "unit": "SKUs", "period": f"through {day}", "source": SOURCE}]
        opts = [_fix_option(iid, {"report_to": "corporate", "skus": [o["sku"] for o in orphans][:20]},
                            "Report the unknown codes to corporate.", ["Without cost or category there is no margin or reorder."], day),
                _nothing(iid, total, "The sales stay without cost, margin or reorder.")]
        out.append(_issue(store_id, "orphan_sku", "SKU-7xxxxx", as_of, ref, 0.0, ev,
                          ["These codes do not exist in the product master even after normalising the key."], opts,
                          opts[0]["option_id"], category="integrity", integrity=True, exposure_usd=total))
    return out
