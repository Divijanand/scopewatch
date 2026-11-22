from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.model.simulate import (DETONATION_AFTER_PLANT_S, PRE_PLANT_LIMIT_S, Simulator, fit_simulator,
                                   simulate, simulate_round)
from scripts.eval_synthetic import build_weighted_train, synthetic_states


def _row(rk, t, a, d, planted=False, since_plant=0.0, label=1, att=20000, dfn=20000, series="s1"):
    return dict(series_id=series, round_key=rk, seconds_since_buy_phase_end=t, planted=planted,
                seconds_since_plant=since_plant, attackers_alive=a, defenders_alive=d,
                att_loadout_value=att, def_loadout_value=dfn, att_has_op=False, def_has_op=False, label=label)


def _tiny_states() -> pd.DataFrame:
    return pd.DataFrame([
        _row("r1", 10.0, 5, 4),
        _row("r1", 30.0, 5, 4, planted=True),
        _row("r1", 40.0, 5, 3, planted=True, since_plant=10.0),
        _row("r2", 18.0, 4, 5, label=0, att=15000, dfn=22000),
        _row("r2", 25.0, 3, 5, label=0, att=15000, dfn=22000),
    ])


def _fixed(kill_rate=0.2, share=0.5, plant=0.0, plant_times=(50.0,), defuse=0.5):
    keys = [(a, d, p) for a in range(6) for d in range(6) for p in (0, 1)]
    return Simulator(
        kill_rate={k: kill_rate for k in keys},
        kill_share_att={k + (e,): share for k in keys for e in ("att_ahead", "even", "def_ahead")},
        plant_prob={(a, d): plant for a in range(6) for d in range(6)},
        plant_times=np.array(plant_times),
        defuse_prob={(d, b): defuse for d in range(6) for b in range(3)},
        starts=pd.DataFrame([dict(att_loadout_value=20000.0, def_loadout_value=20000.0,
                                  att_has_op=False, def_has_op=False)]),
    )


START = pd.Series(dict(att_loadout_value=20000.0, def_loadout_value=20000.0, att_has_op=False, def_has_op=False))


def test_side_wiped_without_plant_loses():
    rows, result = simulate_round(_fixed(share=0.0), np.random.default_rng(0), START)   # attackers never kill
    assert result == 0 and rows[-1]["attackers_alive"] == 0
    rows, result = simulate_round(_fixed(share=1.0), np.random.default_rng(0), START)   # attackers always kill
    assert result == 1 and rows[-1]["defenders_alive"] == 0


def test_timeout_without_plant_is_a_defender_win():
    rows, result = simulate_round(_fixed(kill_rate=1e-6), np.random.default_rng(0), START)
    assert result == 0 and rows == []      # no kill before 100 s, no plant: no state, defenders win


def test_detonation_is_an_attacker_win():
    sim = _fixed(kill_rate=1e-6, plant=1.0, plant_times=(50.0,))
    rows, result = simulate_round(sim, np.random.default_rng(0), START)
    assert result == 1
    assert len(rows) == 1 and rows[0]["planted"] and rows[0]["seconds_since_buy_phase_end"] == 50.0
    assert (PRE_PLANT_LIMIT_S, DETONATION_AFTER_PLANT_S) == (100.0, 45.0)


def test_every_row_of_a_round_has_the_round_result():
    out = simulate(fit_simulator(_tiny_states()), n_rounds=200, seed=3)
    assert (out.groupby("round_key")["label"].nunique() == 1).all()


def test_alive_counts_stay_in_bounds():
    out = simulate(fit_simulator(_tiny_states()), n_rounds=200, seed=3)
    assert out["attackers_alive"].between(0, 5).all() and out["defenders_alive"].between(0, 5).all()


def test_seed_determinism_and_schema():
    sim = fit_simulator(_tiny_states())
    a, b, c = simulate(sim, 20, seed=1), simulate(sim, 20, seed=1), simulate(sim, 20, seed=2)
    assert a.equals(b) and not a.equals(c)
    assert {"label", "series_id", "round_key"} <= set(a.columns)
    assert a["series_id"].str.startswith("synth-").all()


def test_smoothed_next_kill_share():
    # From the hidden 5v5 start: r1 (even economy) opens with an attacker kill;
    # r2 (defenders 7,000 ahead) opens with a defender kill. Add-one smoothing on each cell.
    sim = fit_simulator(_tiny_states())
    assert sim.kill_share_att[(5, 5, 0, "even")] == pytest.approx((1 + 1) / (1 + 2))
    assert sim.kill_share_att[(5, 5, 0, "def_ahead")] == pytest.approx((0 + 1) / (1 + 2))


def test_kill_rate_uses_time_at_risk():
    # r1: 5v5 from 0 s to the kill at 10 s; r2: 5v5 from 0 s to the kill at 18 s -> 2 kills in 28 s
    sim = fit_simulator(_tiny_states())
    assert sim.kill_rate[(5, 5, 0)] == pytest.approx(2 / 28)


def test_weighting_helper_and_series_collision_guard():
    real = _tiny_states()
    synth = simulate(fit_simulator(real), n_rounds=5, seed=7)
    train, w = build_weighted_train(real, synth, 0.25)
    assert len(train) == len(real) + len(synth)
    assert (w[: len(real)] == 1.0).all() and (w[len(real):] == 0.25).all()
    bad = synth.assign(series_id=real.iloc[0]["series_id"])
    with pytest.raises(ValueError):
        build_weighted_train(real, bad, 0.25)


def test_synthetic_ids_never_look_real():
    synth = simulate(fit_simulator(_tiny_states()), n_rounds=50, seed=0)
    assert not synth["series_id"].str.fullmatch(r"\d+").any()


def test_synthetic_states_hits_the_count():
    synth = synthetic_states(fit_simulator(_tiny_states()), 137)
    assert len(synth) == 137
