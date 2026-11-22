"""Step 5: a simple round simulator, fit only on the states it's given (train series only).

States follow `winprob.get_training_data()`: one row after every kill and after the plant, each labelled with
the round's final result (1 = attackers won). The simulator plays a round as a chain of kills and at most one
plant, then labels every row of that round with how it ended.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.model.winprob import FEATURES

# Game rules, checked on our data (2026-11-20):
# - before a plant the round lasts 100 s (the 99.9th percentile of pre-plant kill times is 99.96 s);
#   time running out with no plant means defenders win;
# - the spike detonates 45.0 s after the plant (every detonation is 45.0-45.02 s); detonation means attackers win;
# - a side with nobody alive loses, except after a plant, where the defuse rule decides.
PRE_PLANT_LIMIT_S = 100.0
DETONATION_AFTER_PLANT_S = 45.0
ECON_GAP = 5000.0
DEFAULT_KILL_RATE = 0.12      # per second, only for alive states never seen in fitting
TIME_LEFT_EDGES = (10.0, 25.0)  # defuse buckets: <= 10 s left, 10-25 s, > 25 s


@dataclass(frozen=True)
class Simulator:
    kill_rate: dict          # (att alive, def alive, planted) -> kills per second
    kill_share_att: dict     # (att alive, def alive, planted, econ bucket) -> P(next kill is by the attackers)
    plant_prob: dict         # (att alive, def alive) -> P(plant before the next kill), pre-plant only
    plant_times: np.ndarray  # real plant times (s since buy-phase end)
    defuse_prob: dict        # (def alive, time-left bucket) -> P(defuse) once the attackers are all dead
    starts: pd.DataFrame     # real round starts: loadouts and Operator holders, kept together


def econ_bucket(att_loadout_value: float, def_loadout_value: float) -> str:
    d = float(att_loadout_value) - float(def_loadout_value)
    if d > ECON_GAP:
        return "att_ahead"
    if d < -ECON_GAP:
        return "def_ahead"
    return "even"


def time_left_bucket(time_left: float) -> int:
    return int(np.searchsorted(TIME_LEFT_EDGES, time_left, side="left"))


def smooth(k: float, n: float) -> float:
    """Add-one smoothing: never exactly 0 or 1."""
    return float((k + 1.0) / (n + 2.0))


def _with_start_rows(states: pd.DataFrame) -> pd.DataFrame:
    """Real states start after the first event; add a hidden 5v5 row at 0 s per round so the time to the
    first kill is learned too. Start rows are only used for fitting, never emitted."""
    first = states.sort_values(["round_key", "seconds_since_buy_phase_end"]).groupby("round_key", as_index=False).first()
    start = first.assign(seconds_since_buy_phase_end=0.0, planted=False, seconds_since_plant=0.0,
                         attackers_alive=5, defenders_alive=5)
    return pd.concat([start, states], ignore_index=True)


def fit_simulator(states: pd.DataFrame) -> Simulator:
    df = _with_start_rows(states)
    df["planted"] = df["planted"].astype(bool)
    df = df.sort_values(["round_key", "seconds_since_buy_phase_end", "planted"], kind="stable").reset_index(drop=True)
    nxt = df.groupby("round_key")[["seconds_since_buy_phase_end", "attackers_alive", "defenders_alive", "planted"]].shift(-1)
    has_next = nxt["seconds_since_buy_phase_end"].notna()
    att_down = has_next & (nxt["attackers_alive"] < df["attackers_alive"])
    def_down = has_next & (nxt["defenders_alive"] < df["defenders_alive"])
    df["next_kill"] = att_down | def_down
    df["next_kill_by_att"] = def_down & ~att_down
    df["next_plant"] = has_next & ~df["planted"] & nxt["planted"].fillna(False).astype(bool)
    df["dt"] = (nxt["seconds_since_buy_phase_end"] - df["seconds_since_buy_phase_end"]).clip(lower=0.0)
    df["econ"] = np.where(df["att_loadout_value"] - df["def_loadout_value"] > ECON_GAP, "att_ahead",
                          np.where(df["att_loadout_value"] - df["def_loadout_value"] < -ECON_GAP, "def_ahead", "even"))
    a, d, p = df["attackers_alive"].astype(int), df["defenders_alive"].astype(int), df["planted"].astype(int)
    df["a"], df["d"], df["p"] = a, d, p

    # time to the next kill: exponential, rate = kills / time at risk (rows whose next event is known)
    known = df[has_next]
    g = known.groupby(["a", "d", "p"]).agg(kills=("next_kill", "sum"), exposure=("dt", "sum"))
    kill_rate = {k: float(r.kills / r.exposure) if r.exposure > 0 and r.kills > 0 else DEFAULT_KILL_RATE
                 for k, r in g.iterrows()}

    # who gets the next kill
    kills = df[df["next_kill"]]
    g = kills.groupby(["a", "d", "p", "econ"]).agg(k=("next_kill_by_att", "sum"), n=("next_kill", "size"))
    kill_share_att = {k: smooth(r.k, r.n) for k, r in g.iterrows()}

    # plant before the next kill (pre-plant rows whose next event is a kill or the plant)
    pre = df[~df["planted"] & (df["next_kill"] | df["next_plant"])]
    g = pre.groupby(["a", "d"]).agg(k=("next_plant", "sum"), n=("next_plant", "size"))
    plant_prob = {k: smooth(r.k, r.n) for k, r in g.iterrows()}

    plants = df[df["planted"]].groupby("round_key")["seconds_since_buy_phase_end"].min()
    plant_times = np.sort(plants.to_numpy(dtype=float)) if len(plants) else np.array([55.0])

    # defuse: first post-plant row with no attackers alive; defenders win (label 0) = defused
    dead = df[df["planted"] & (df["attackers_alive"] == 0)].groupby("round_key").first()
    dead = dead.assign(bucket=[time_left_bucket(DETONATION_AFTER_PLANT_S - s) for s in dead["seconds_since_plant"]])
    g = dead.groupby(["d", "bucket"]).agg(k=("label", lambda s: int((s == 0).sum())), n=("label", "size"))
    defuse_prob = {k: smooth(r.k, r.n) for k, r in g.iterrows()}

    starts = (states.sort_values(["round_key", "seconds_since_buy_phase_end"]).groupby("round_key").first()
              [["att_loadout_value", "def_loadout_value", "att_has_op", "def_has_op"]].reset_index(drop=True))
    return Simulator(kill_rate, kill_share_att, plant_prob, plant_times, defuse_prob, starts)


def simulate_round(sim: Simulator, rng: np.random.Generator, start) -> tuple[list[dict], int]:
    """Play one round. Returns its rows (without labels) and the result (1 = attackers won)."""
    econ = econ_bucket(start.att_loadout_value, start.def_loadout_value)
    a, d, t, plant_t = 5, 5, 0.0, None
    rows = []

    def emit():
        rows.append(dict(seconds_since_buy_phase_end=t, planted=plant_t is not None,
                         seconds_since_plant=0.0 if plant_t is None else t - plant_t,
                         attackers_alive=a, defenders_alive=d,
                         att_loadout_value=float(start.att_loadout_value), def_loadout_value=float(start.def_loadout_value),
                         att_has_op=bool(start.att_has_op), def_has_op=bool(start.def_has_op)))

    while True:
        planted = plant_t is not None
        if not planted and rng.random() < sim.plant_prob.get((a, d), 0.0):
            later = sim.plant_times[(sim.plant_times > t) & (sim.plant_times < PRE_PLANT_LIMIT_S)]
            if len(later):
                t = float(rng.choice(later))
                plant_t = t
                emit()
                continue
        rate = sim.kill_rate.get((a, d, int(planted)), DEFAULT_KILL_RATE)
        t_kill = t + float(rng.exponential(1.0 / rate))
        if not planted and t_kill >= PRE_PLANT_LIMIT_S:
            return rows, 0                                    # time runs out, no plant: defenders win
        if planted and t_kill >= plant_t + DETONATION_AFTER_PLANT_S:
            return rows, 1                                    # detonation: attackers win
        t = t_kill
        if rng.random() < sim.kill_share_att.get((a, d, int(planted), econ), 0.5):
            d -= 1
        else:
            a -= 1
        emit()
        if d == 0:
            return rows, 1
        if a == 0:
            if not planted:
                return rows, 0
            left = plant_t + DETONATION_AFTER_PLANT_S - t
            p_defuse = sim.defuse_prob.get((d, time_left_bucket(left)), 0.5)
            return rows, 0 if rng.random() < p_defuse else 1


def simulate(sim: Simulator, n_rounds: int, seed: int) -> pd.DataFrame:
    """`n_rounds` rounds as states with exactly `winprob.FEATURES` plus label, series_id and round_key.
    Deterministic for a seed. Every row of a round carries that round's result, as in the real data."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n_rounds):
        start = sim.starts.iloc[int(rng.integers(0, len(sim.starts)))]
        rows, result = simulate_round(sim, rng, start)
        for r in rows:
            r.update(label=result, series_id=f"synth-{seed}-{i}", round_key=f"synth-{seed}-{i}:1")
        out.extend(rows)
    df = pd.DataFrame(out, columns=FEATURES + ["label", "series_id", "round_key"])
    return df.astype({"planted": bool, "att_has_op": bool, "def_has_op": bool, "label": int})


def compare_to_real(sim_states: pd.DataFrame, real_states: pd.DataFrame) -> pd.DataFrame:
    def summarize(df):
        df = df.sort_values(["round_key", "seconds_since_buy_phase_end"])
        last = df.groupby("round_key").tail(1)
        rounds = df.groupby("round_key")
        kills = 10 - last["attackers_alive"] - last["defenders_alive"]
        n = len(df)
        return dict(
            attacker_win_rate=float(last["label"].mean()),
            plant_rate=float(rounds["planted"].max().mean()),
            kills_per_round=float(kills.mean()),
            states_per_round=float(n / len(last)),
            share_1v1=float(((df["attackers_alive"] == 1) & (df["defenders_alive"] == 1)).mean()),
            share_1v2=float(((df["attackers_alive"] == 1) & (df["defenders_alive"] == 2)).mean()),
            share_2v1=float(((df["attackers_alive"] == 2) & (df["defenders_alive"] == 1)).mean()),
        )

    a, b = summarize(sim_states), summarize(real_states)
    return pd.DataFrame([dict(metric=k, synthetic=a[k], real=b[k]) for k in a])
