"""CLI: python3 -m glazed_etl --raw <raw dir> --out <clean dir>"""
from __future__ import annotations

import argparse
import sys
import time

from . import pipeline


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="glazed_etl", description="Clean the Glazed Co. raw CSVs (read-only input).")
    ap.add_argument("--raw", required=True, help="directory with the 13 raw CSV files")
    ap.add_argument("--out", required=True, help="output directory (parquet, glazed.duckdb, dq_log.csv, validation.json)")
    args = ap.parse_args(argv)
    t0 = time.time()
    res = pipeline.run(args.raw, args.out)
    print(f"{'table':<18}{'raw':>10}{'clean':>10}")
    for t, c in res["row_counts"].items():
        print(f"{t:<18}{c['raw']:>10,}{c['clean']:>10,}")
    print(f"\nDQ log entries: {res['dq_entries']}  ->  {res['out_dir']}/dq_log.csv")
    print("Validation:")
    for name, chk in res["validation"]["checks"].items():
        print(f"  {'PASS' if chk['ok'] else 'FAIL'}  {name}")
    k = res["validation"]["checks"]["sales_vs_kpi"]
    print(f"  sales vs KPI: {k['within_1pct']:,}/{k['store_days_compared']:,} store-days within 1% ({k['within_1pct_share']:.1%})")
    print(f"Done in {time.time() - t0:.1f}s")
    return 0 if res["validation"]["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
