from datetime import date

from glazed_backend.metrics.issues import finalize_options
from glazed_backend.metrics.promo_audit import PromoRef, audit_promo, promo_issue
from glazed_backend.metrics.types import Config


def ref(pid, dep, disc, uplift, margin, start="2026-01-01", end="2026-01-14", cat=None, placebo=False):
    return PromoRef(pid, pid, dep, cat, disc, date.fromisoformat(start), date.fromisoformat(end), uplift, margin,
                    "baseline", placebo)


REFS = [ref("PR002", "Bakery", 15, -11, -103000), ref("PR005", "Bakery", 15, 1, -30000),
        ref("PR008", "Bakery", 25, 35, -3600), ref("PR013", "Bakery", 15, 14, 0, placebo=True),
        ref("PR009", "Beverage", 15, 30, 26000), ref("PR004", "Food", 12, 25, 7000)]
AS_OF = date(2026, 9, 1)


def test_bakery_15_is_blocked_citing_the_promos_that_destroyed_margin_and_alternative_is_the_best_roi():
    a = audit_promo(REFS, "bakery", 15, AS_OF)
    assert a["verdict"] == "block" and a["recommendation"] == "do_nothing"
    assert [s["promo_id"] for s in a["similar"]] == ["PR002", "PR005"]  # PR008 is 10 points away, PR013 is the placebo
    assert a["noise_floor_pct"] == 10.0 and a["alternative"]["promo_id"] == "PR009"
    assert any("PR002" in r for r in a["reasons"])


def test_a_clear_winner_is_allowed_and_no_history_is_insufficient_evidence():
    ok = audit_promo(REFS, "Beverage", 15, AS_OF)
    assert ok["verdict"] == "allow" and ok["recommendation"] == "run_promo"
    none = audit_promo(REFS, "Merchandise", 20, AS_OF)
    assert none["verdict"] == "insufficient_evidence" and none["similar"] == []


def test_uplift_under_the_noise_floor_blocks_even_with_positive_margin():
    a = audit_promo([ref("PRX", "Food", 10, 4, 500)], "Food", 10, AS_OF)
    assert a["verdict"] == "block" and "noise floor" in " ".join(a["reasons"])


def test_only_promos_finished_by_as_of_count():
    future = [ref("PR002", "Bakery", 15, -11, -103000, start="2026-09-10", end="2026-09-20")]
    assert audit_promo(future, "Bakery", 15, AS_OF)["verdict"] == "insufficient_evidence"


def test_blocked_promo_issue_recommends_do_nothing_and_offers_the_alternative():
    a = audit_promo(REFS, "Bakery", 15, AS_OF)
    iss = promo_issue("S030", AS_OF, AS_OF, {"promo_id": "PR099", "name": "Bakery 15", "department": "Bakery",
                                             "discount_pct": 15.0, "start": "2026-09-03"}, a, 38, Config())
    assert iss["kind"] == "misleading_promo" and iss["issue_id"] == "S030|misleading_promo|PR099"
    acts = [o["action_type"] for o in iss["options"]]
    assert acts == ["do_nothing", "run_promo"] and iss["severity_usd"] > 0
    assert iss["recommended_option_id"] == iss["options"][0]["option_id"]
    assert iss["options"][1]["params"]["promo_ref"] == "PR009"
    finalize_ok = [o["tier"] for o in iss["options"]]
    assert all(t in ("N0", "N1", "N2", "N3") for t in finalize_ok)
    assert any("chain-wide" in c for c in iss["data_caveats"])
