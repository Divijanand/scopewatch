import numpy as np
import pandas as pd
import pytest

from engine import clustering
from engine.metrics.core import Rate, bootstrap_mean
from engine.metrics.duels import section
from engine.report import checks, select, summarize
from scripts.eval_ranges import estimate_rho
from engine.significance import benjamini_hochberg, mean_p, rate_p, two_rates_p


def _r(k, n, deff=1.0):
    r = Rate.of(k, n, deff)
    return dict(k=r.k, n=r.n, p=r.p, lo=r.lo, hi=r.hi, small_sample=r.small_sample, deff=r.deff)


def test_benjamini_hochberg_known_example():
    assert benjamini_hochberg([0.001, 0.02, 0.04, 0.6], q=0.05) == [True, True, False, False]
    # 0.04 fails its own line, but a smaller-ranked p passes; a p that passes carries every smaller one with it
    assert benjamini_hochberg([0.04, 0.045, 0.049], q=0.05) == [True, True, True]


def test_checks_that_could_not_run_are_not_counted():
    assert benjamini_hochberg([None, 0.04, None], q=0.05) == [False, True, False]
    assert benjamini_hochberg([], q=0.05) == []


def test_clustering_makes_the_same_gap_weaker():
    assert rate_p(_r(62, 100, 2.37), 0.5) > rate_p(_r(62, 100), 0.5)
    assert two_rates_p(_r(30, 100, 2.37), _r(50, 100)) > two_rates_p(_r(30, 100), _r(50, 100))
    assert rate_p(_r(62, 100), 0.5) == pytest.approx(0.0164, abs=1e-3)


def test_one_sided_checks_only_their_own_direction():
    assert rate_p(_r(62, 100), 0.5, direction="higher") == pytest.approx(rate_p(_r(62, 100), 0.5) / 2)
    assert rate_p(_r(62, 100), 0.5, direction="lower") > 0.98
    assert two_rates_p(_r(30, 100), _r(50, 100), direction="lower") < 0.01


def test_small_samples_and_missing_league_are_not_checks():
    assert rate_p(_r(5, 6), 0.5) is None
    assert rate_p(_r(62, 100), None) is None


def test_the_range_and_the_p_value_use_the_same_design_effect():
    plain, wide = _r(60, 100), _r(60, 100, 2.0)
    assert (wide["k"], wide["n"], wide["p"]) == (60, 100, 0.6)          # the sample shown doesn't change
    assert wide["lo"] < plain["lo"] and wide["hi"] > plain["hi"]
    half = Rate.of(30, 50)                                             # 100 rounds at deff 2 = 50 independent rounds
    assert (wide["lo"], wide["hi"]) == (half.lo, half.hi)
    assert rate_p(wide, 0.5) == pytest.approx(rate_p(_r(30, 50), 0.5))


def test_design_effect_depends_on_rounds_per_game(monkeypatch):
    monkeypatch.setattr(clustering, "RHO", {"m": 0.1})
    one_game = [f"g:{i}" for i in range(11)]
    own_games = [f"g{i}:1" for i in range(11)]
    assert clustering.design_effect("m", one_game) == pytest.approx(2.0)
    assert clustering.design_effect("m", own_games) == 1.0              # pistols: one per game, nothing repeats
    uneven = [f"a:{i}" for i in range(9)] + ["b:1"]
    assert clustering.design_effect("m", uneven) == pytest.approx(1 + (82 / 10 - 1) * 0.1)
    assert clustering.design_effect("m", []) == 1.0


def test_over_counts_rows_and_keys_the_same(monkeypatch):
    monkeypatch.setattr(clustering, "RHO", {"m": 0.1})
    rows = [(f"g{i % 2}:{i}", i < 6) for i in range(20)]
    a = Rate.over("m", [r for r in rows if r[1]], rows)
    b = Rate.over("m", [r[0] for r in rows if r[1]], [r[0] for r in rows])
    assert a == b and (a.k, a.n) == (6, 20) and a.deff == pytest.approx(1.9)


def test_rho_estimate_finds_a_known_correlation():
    rng = np.random.default_rng(4)
    data = {}
    for t in range(150):
        p = rng.beta(4.5, 4.5, 12)                                     # beta-binomial: rho = 1 / (a + b + 1) = 0.1
        data[("t", t, "x")] = [("clustered", {str(g): (int(rng.binomial(12, p[g])), 12) for g in range(12)}),
                               ("independent", {str(g): (int(rng.binomial(12, 0.5)), 12) for g in range(12)})]
    rho = estimate_rho(data)
    assert rho["clustered"][0] == pytest.approx(0.1, abs=0.02)
    assert rho["independent"][0] == pytest.approx(0.0, abs=0.01)


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
