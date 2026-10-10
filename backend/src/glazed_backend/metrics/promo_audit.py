"""Alert 7: audit a proposed promotion against what similar promotions did, versus the PR013 noise floor.

`PromoRef` rows come from the Datos baseline (`data/docs/analisis_estado.md` section 3: chain-wide difference-in-
differences uplift and margin effect with an assumed cost [S]), joined to the `promotions` table. PR013 never ran,
so its drift in Bakery is the placebo: the method's noise is about +-10 points. Nothing here does I/O."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .issues import _issue, finalize_options
from .options import make_option
from .types import Config

NOISE_FLOOR_PCT = 10.0  # +-10 points, placebo PR013
SIMILAR_DISCOUNT_POINTS = 5.0

# promo_id -> (uplift %, chain-wide net margin effect USD, confidence). Source: data/docs/analisis_estado.md section 3.
BASELINE: dict[str, tuple[float, float, str]] = {
    "PR001": (15.0, -6000.0, "low"), "PR002": (-11.0, -103000.0, "medium"), "PR003": (1.5, -4000.0, "medium"),
    "PR004": (25.0, 7000.0, "medium"), "PR005": (1.0, -30000.0, "medium"), "PR006": (11.0, -9000.0, "medium"),
    "PR007": (19.0, 400.0, "medium"), "PR008": (35.0, -3600.0, "medium"), "PR009": (30.0, 26000.0, "medium"),
    "PR010": (8.0, -12000.0, "medium"), "PR011": (-4.0, -20000.0, "low"), "PR012": (16.0, 4000.0, "medium"),
    "PR013": (14.0, 0.0, "placebo"),
}
SOURCE = "data/docs/analisis_estado.md section 3 (chain-wide DiD, margin with assumed cost)"


@dataclass(frozen=True)
class PromoRef:
    promo_id: str
    name: str
    department: str
    category: str | None
    discount_pct: float
    start: date
    end: date
    uplift_pct: float
    margin_effect_usd: float
    confidence: str
    placebo: bool = False

    def brief(self) -> dict:
        return {"promo_id": self.promo_id, "name": self.name, "department": self.department,
                "category": self.category, "discount_pct": self.discount_pct, "uplift_pct": self.uplift_pct,
                "margin_effect_usd": self.margin_effect_usd, "confidence": self.confidence,
                "period": f"{self.start.isoformat()}..{self.end.isoformat()}", "source": SOURCE}


def _money(x: float) -> str:
    return f"{'-' if x < 0 else '+'}${abs(x):,.0f}"


def audit_promo(refs: list[PromoRef], department: str, discount_pct: float, as_of: date,
                noise_floor_pct: float = NOISE_FLOOR_PCT) -> dict:
    """Verdict for a proposed promo (department + discount %). Rule: block when the uplift of similar past promos
    is under the noise floor OR their margin effect is negative. Only promos finished by `as_of` count."""
    done = [r for r in refs if not r.placebo and r.end <= as_of]
    dep = department.strip().lower()
    similar = [r for r in done if r.department.lower() == dep and abs(r.discount_pct - discount_pct) <= SIMILAR_DISCOUNT_POINTS]
    good = [r for r in done if r.uplift_pct >= noise_floor_pct and r.margin_effect_usd > 0]
    best = max(good, key=lambda r: (r.margin_effect_usd, r.promo_id), default=None)
    out = {"department": department, "discount_pct": discount_pct, "as_of": as_of.isoformat(),
           "noise_floor_pct": noise_floor_pct, "noise_floor_source": "PR013 placebo (never ran): +-10 points",
           "similar": [r.brief() for r in sorted(similar, key=lambda r: r.promo_id)],
           "alternative": best.brief() if best else None, "reasons": [], "method_source": SOURCE}
    if not similar:
        return {**out, "verdict": "insufficient_evidence", "recommendation": None,
                "reasons": [f"No finished promotion in {department} within {SIMILAR_DISCOUNT_POINTS:g} points of "
                            f"{discount_pct:g}% before {as_of.isoformat()}."]}
    uplift = sum(r.uplift_pct for r in similar) / len(similar)
    margin = sum(r.margin_effect_usd for r in similar)
    reasons = []
    if uplift < noise_floor_pct:
        reasons.append(f"Mean uplift of similar promos is {uplift:+.1f}%, under the {noise_floor_pct:g}-point noise floor "
                       f"({', '.join(r.promo_id for r in similar)}).")
    if margin < 0:
        reasons.append("Margin effect was negative: " + ", ".join(f"{r.promo_id} {_money(r.margin_effect_usd)}" for r in similar)
                       + f" ({_money(margin)} in total).")
    out.update(mean_uplift_pct=round(uplift, 1), total_margin_effect_usd=round(margin, 2))
    if reasons:
        return {**out, "verdict": "block", "recommendation": "do_nothing", "reasons": reasons}
    return {**out, "verdict": "allow", "recommendation": "run_promo",
            "reasons": [f"Similar promos beat the noise floor ({uplift:+.1f}%) with a positive margin ({_money(margin)})."]}


def promo_issue(store_id: str, as_of: date, ref: date, promo: dict, audit: dict, n_stores: int, cfg: Config) -> dict:
    """Issue for a blocked proposed promo: block it (do_nothing) and offer the best historical promo instead.
    Chain-wide margin effects are split evenly over the stores (an average-store estimate, not this store's)."""
    iid = f"{store_id}|misleading_promo|{promo['promo_id']}"
    share = max(1, n_stores)
    avoided = max(0.0, -float(audit.get("total_margin_effect_usd", 0.0))) / max(1, len(audit["similar"])) / share
    urgency = {"deadline_date": promo.get("start"), "reason": "Decide before the promotion starts."}
    zero = {"low": 0.0, "mid": avoided, "high": avoided}
    block = make_option(iid, "do_nothing", {"blocks": promo["promo_id"], "department": promo["department"],
                                            "discount_pct": promo["discount_pct"]},
                        {"benefit": zero, "cost_usd": 0.0, "net_mid": avoided, "waste_delta": 0.0, "lost_delta": 0.0},
                        urgency, ["Blocking is reversible; the manager can still approve the promotion."],
                        cost_of_inaction_usd={"mid": round(avoided, 2)}, label="Block this promotion")
    options = [block]
    alt = audit.get("alternative")
    if alt:
        mid = float(alt["margin_effect_usd"]) / share
        ev = {"benefit": {"low": mid * 0.5, "mid": mid, "high": mid * 1.5}, "cost_usd": 0.0, "net_mid": mid,
              "waste_delta": 0.0, "lost_delta": 0.0}
        options.append(make_option(iid, "run_promo",
                                   {"promo_ref": alt["promo_id"], "department": alt["department"],
                                    "category": alt["category"], "discount_pct": alt["discount_pct"]},
                                   ev, urgency, ["Historical result of another period and category; seasonality differs."],
                                   data_caveat="chain-wide historical effect, split evenly across stores"))
    rec = finalize_options(options, "misleading_promo", {}, cfg)
    rec = block["option_id"]  # the rule blocks: recommend not running it, never publish silently
    ev = [{"metric": "similar_promo", "value": f"{s['promo_id']} uplift {s['uplift_pct']:+g}%, margin {_money(s['margin_effect_usd'])}",
           "unit": "text", "period": s["period"], "source": SOURCE} for s in audit["similar"]]
    ev.append({"metric": "noise_floor", "value": audit["noise_floor_pct"], "unit": "uplift points",
               "period": "PR013 placebo", "source": SOURCE})
    return _issue(store_id, "misleading_promo", promo["promo_id"], as_of, ref, avoided, ev,
                  ["Effects are chain-wide differences-in-differences (assumed cost); the per-store figure splits them evenly "
                   "across stores.", *audit["reasons"]], options, rec, promo_id=promo["promo_id"],
                  product_name=promo.get("name"), promo={"department": promo["department"],
                                                         "discount_pct": promo["discount_pct"]}, audit=audit)
