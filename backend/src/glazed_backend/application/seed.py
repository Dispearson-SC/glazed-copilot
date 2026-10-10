"""Baseline experiences parsed from Dataset/analisis_estado.md section 3 (promo evaluations)."""
from __future__ import annotations

import re

from ..domain import Experience

_NOTE = ("Baseline (chain-wide, DiD method, margin effect uses an assumed cost [S]; "
         "PR001 and PR011 low confidence).")


def parse_promo_baseline(markdown: str, store_id: str = "baseline") -> list[Experience]:
    m = re.search(r"^## 3\..*?$(.*?)(?=^## )", markdown, re.S | re.M)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        cells = [c.strip().strip("*") for c in line.strip().strip("|").split("|")]
        if len(cells) != 6 or not re.match(r"PR\d+", cells[0]):
            continue
        promo, kind, expected, uplift, cost, net = cells
        pid = promo.split()[0]
        text = (f"[{store_id} · promo_evaluation · {pid} · baseline] {promo} ({kind}): expected uplift {expected}%, "
                f"measured uplift {uplift.replace('*', '')} (+-28d, in parentheses +-14d), discount cost {cost}, "
                f"net margin effect {net.replace('*', '')}. {_NOTE}")
        out.append(Experience(text, "promo_evaluation", store_id))
    return out
