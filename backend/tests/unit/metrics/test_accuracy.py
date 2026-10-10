from glazed_backend.metrics.accuracy import (ScoredPoint, censored_pinball_loss, pinball_loss, segment, shelf_life_class,
                                              summarize)


def pt(actual, forecast, p10=None, p90=None, censored=False, baseline=None, levels=()):
    return ScoredPoint(actual, forecast, forecast - 2 if p10 is None else p10, forecast + 2 if p90 is None else p90,
                       censored, baseline, tuple(levels))


def test_pinball_penalizes_under_prediction_by_q_and_over_prediction_by_one_minus_q():
    assert pinball_loss(10, 6, 0.74) == pytest_approx(0.74 * 4)
    assert pinball_loss(10, 14, 0.74) == pytest_approx(0.26 * 4)
    assert pinball_loss(10, 10, 0.74) == 0.0


def pytest_approx(x):
    import pytest
    return pytest.approx(x)


def test_censored_pinball_is_one_sided_only_a_prediction_below_the_actual_counts():
    assert censored_pinball_loss(10, 14, 0.74) == 0.0  # above a lower bound is never a miss
    assert censored_pinball_loss(10, 6, 0.74) == pytest_approx(0.74 * 4)


def test_summary_wape_bias_coverage_and_baseline_wape_over_uncensored_days():
    pts = [pt(10, 8, baseline=12), pt(10, 13, p10=11, p90=12, baseline=9)]  # second one outside the band
    s = summarize(pts)
    assert s["n_days"] == 2 and s["wape"] == pytest_approx(5 / 20) and s["bias"] == pytest_approx(1 / 20)
    assert s["coverage_p10_p90"] == pytest_approx(0.5) and s["wape_baseline"] == pytest_approx(3 / 20)


def test_pinball_074_interpolates_the_level_between_p50_and_p80():
    p = pt(10, 8, levels=[(0.5, 8.0), (0.8, 14.0)])  # q74 = 8 + 0.8 * 6 = 12.8
    assert summarize([p])["pinball_074"] == pytest_approx(0.26 * 2.8)


def test_censored_days_are_excluded_from_accuracy_and_scored_one_sided():
    pts = [pt(10, 10), pt(20, 25, censored=True), pt(20, 15, censored=True)]
    s = summarize(pts)
    assert s["n_days"] == 1 and s["n_censored"] == 2 and s["wape"] == 0.0
    assert s["censored_coverage"] == 0.5  # forecast >= actual covers; 15 < 20 is a miss
    assert s["censored_pinball_074"] == pytest_approx(0.74 * 3.8 / 2)  # q74 of the 15 forecast = 15 + 0.6 * 2 = 16.2


def test_empty_summary_has_nulls_not_zeros():
    s = summarize([])
    assert s["n_days"] == 0 and s["wape"] is None and s["bias"] is None and s["censored_coverage"] is None


def test_zero_actuals_give_no_wape():
    assert summarize([pt(0, 3)])["wape"] is None


def test_shelf_life_classes():
    assert [shelf_life_class(x) for x in (1, 0, 2, 3, 5, 14, 60, 730, None)] == \
        ["1", "1", "2-3", "2-3", "4-14", "4-14", "non_perishable", "non_perishable", "non_perishable"]


def test_segment_groups_points_by_key():
    out = segment([("a", pt(10, 10)), ("b", pt(10, 5)), ("a", pt(10, 12))])
    assert set(out) == {"a", "b"} and out["a"]["n_days"] == 2 and out["b"]["bias"] == -0.5
