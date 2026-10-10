"""CLI: python3 -m forecast run --clean ../clean --out out"""
from __future__ import annotations

import argparse
import sys

from forecast import pipeline


def _one(x: str):
    x = x.strip().lower()
    return None if x == "none" else int(x)


def _half_lives(s: str):
    """'none,30,14/none' -> [None, 30, (14, None)]  (a/b = level half-life / coefficient half-life)"""
    out = []
    for tok in s.split(","):
        out.append(tuple(_one(p) for p in tok.split("/")) if "/" in tok else _one(tok))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="forecast")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="train on the first 80%% of the span and score the last 20%%")
    r.add_argument("--clean", default="../clean", help="directory with the cleaned parquet tables (read-only)")
    r.add_argument("--out", default="out")
    r.add_argument("--frac", type=float, default=0.8)
    r.add_argument("--half-lives", type=_half_lives, default=None, help="comma list, e.g. none,30,14/none")
    r.add_argument("--no-center", action="store_true", help="keep the backtest drift in the quantiles (sensitivity)")
    a = ap.parse_args(argv)
    meta = pipeline.run(a.clean, a.out, frac=a.frac, half_lives=a.half_lives, center=not a.no_center)
    print(f"cutoff={meta['cutoff']} half_life={meta['half_life']} leakage_check_passed={meta['leakage_check']['passed']}")
    return 0 if meta["leakage_check"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
