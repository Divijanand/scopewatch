import numpy as np
import pandas as pd
import pytest

from engine.metrics.core import Rate, bootstrap_mean
from engine.metrics.duels import section
from engine.report import checks, select, summarize
from engine.significance import benjamini_hochberg, dispersion, mean_p, rate_p, two_rates_p


def _r(k, n):
    r = Rate.of(k, n)
    return dict(k=r.k, n=r.n, p=r.p, lo=r.lo, hi=r.hi, small_sample=r.small_sample)


def test_benjamini_hochberg_known_example():
    assert benjamini_hochberg([0.001, 0.02, 0.04, 0.6], q=0.05) == [True, True, False, False]
    # 0.04 fails its own line, but a smaller-ranked p passes; a p that passes carries every smaller one with it
    assert benjamini_hochberg([0.04, 0.045, 0.049], q=0.05) == [True, True, True]


def test_checks_that_could_not_run_are_not_counted():
    assert benjamini_hochberg([None, 0.04, None], q=0.05) == [False, True, False]
    assert benjamini_hochberg([], q=0.05) == []


def test_clustering_makes_the_same_gap_weaker():
    assert rate_p(_r(62, 100), 0.5, phi=2.37) > rate_p(_r(62, 100), 0.5, phi=1.0)
    assert rate_p(_r(62, 100), 0.5) == pytest.approx(0.0164, abs=1e-3)


def test_one_sided_checks_only_their_own_direction():
    assert rate_p(_r(62, 100), 0.5, direction="higher") == pytest.approx(rate_p(_r(62, 100), 0.5) / 2)
    assert rate_p(_r(62, 100), 0.5, direction="lower") > 0.98
    assert two_rates_p(_r(30, 100), _r(50, 100), direction="lower") < 0.01


def test_small_samples_and_missing_league_are_not_checks():
    assert rate_p(_r(5, 6), 0.5) is None
    assert rate_p(_r(62, 100), None) is None


def test_unmeasured_dispersion_assumes_the_worst():
    assert dispersion("team.closing.throws") == 2.37
    assert dispersion("att.executes.B") == 1.06


def test_mean_p_agrees_with_the_90_percent_range():
    rng = np.random.default_rng(1)
    for shift in (0.0, 0.1, 0.3):
        v = rng.normal(shift, 1, 200).tolist()
        g = [str(i % 12) for i in range(200)]
        lo, hi = bootstrap_mean(v, g, seed=3)
        assert (mean_p(float(np.mean(v)), lo, hi, 12) < 0.10) == (lo > 0 or hi < 0)


def test_one_series_is_never_beyond_noise():
    g = pd.DataFrame(dict(actual=[1.0] * 60, expected=[0.4] * 60, series_id=["s1"] * 60))
    s = section(g)
    assert s["diff"] == 0.6 and s["p_value"] is None and s["beyond_noise"] is False


def test_one_lucky_check_among_many_is_dropped():
    flat = {"rate": _r(50, 100), "league": {"p": 0.5}}
    lucky = {"site": "L", "rate": _r(61, 100), "league": {"p": 0.5}}       # p of about 0.03 alone
    alone = {"att.executes": {"value": {}, "breakdown": [lucky]}}
    crowd = {"att.executes": {"value": {}, "breakdown": [lucky] + [dict(flat, site=f"S{i}") for i in range(20)]}}
    assert len(summarize(alone, "attacker")[0]) == 1
    assert summarize(crowd, "attacker")[0] == []
    assert len(checks(crowd)) == 21 and select(checks(crowd)) == []
