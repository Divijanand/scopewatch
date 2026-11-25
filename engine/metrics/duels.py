"""Dry duels: fights with no utility from either side, scored against what the opener advantage predicts.

The opener (first gun damage) wins about 83% of fights, so a raw win rate mostly measures who shot first.
Expected = the league's dry-fight opener win rate in the same cell (map, opener side, alive counts, plant),
flipped when the enemy opened. The card's number is actual - expected over the team's dry fights.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from engine.config import V2_DIR
from ..significance import benjamini_hochberg, mean_p
from .core import Filters, MetricDef, MetricResult, bootstrap_mean, metric

FIGHTS_PARQUET = V2_DIR / "models" / "fights.parquet"
MIN_AGENT_FIGHTS = 50
DRY_COLS = [
    "util_opener_flash_stun", "util_opener_smoke", "util_opener_recon", "util_opener_ult", "dmg_util_opener",
    "util_other_flash_stun", "util_other_smoke", "util_other_recon", "util_other_ult", "dmg_util_other",
]
CELL = ["map", "opener_side", "opener_side_alive", "other_side_alive", "planted"]

DRY_DUELS = MetricDef(
    id="fights.dry_duels",
    version=1,
    title="Dry duels",
    question="With no utility around, does the team win more 1v1 fights than the opener advantage alone predicts?",
    population="The team's fights with a winner and no utility from either side in the 4 s before (within 2,500 "
               "units), on one map and side",
    numerator="Fights the team's player won, against the league's dry-fight rate in the same state",
    unit="fights",
    caveats=(
        "A fight = one pair of opposite-side players from the first gun damage until a kill between them; fights "
        "that end with no kill within 3 s aren't counted.",
        "Expected = the league's dry-fight opener win rate for the same map, opener side, alive counts and plant; "
        "1 minus that when the enemy opened.",
        "Dry = no flash, stun, smoke, recon or ult cast near the fight by either team, and no ability damage to "
        "either fighter, in the 4 s before. Utility from further away can still matter.",
        "Ranges are 90% series-bootstrap t intervals (D-020). Association, not cause.",
    ),
)


def dry(df: pd.DataFrame) -> pd.DataFrame:
    mask = np.ones(len(df), dtype=bool)
    for c in DRY_COLS:
        mask &= (pd.to_numeric(df[c], errors="coerce").fillna(0.0) == 0.0).to_numpy()
    return df.loc[mask]


@lru_cache(maxsize=2)
def _load(path: str, mtime: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """All dry fights and the league opener win rate per cell. Cached per file version."""
    df = dry(pd.read_parquet(path))
    df = df.assign(opener_team=df["opener_team"].astype(str), other_team=df["other_team"].astype(str),
                   planted=df["planted"].astype(bool))
    rates = df.groupby(CELL, dropna=False)["label"].mean().rename("opener_rate").reset_index()
    return df, rates


def team_view(df: pd.DataFrame, rates: pd.DataFrame, team_id: str) -> pd.DataFrame:
    """The team's dry fights with actual (1 = the team's player won), expected, and the team's side and agent."""
    team = df[(df["opener_team"] == team_id) | (df["other_team"] == team_id)].merge(rates, on=CELL, how="left")
    opened = (team["opener_team"] == team_id).to_numpy()
    rate = team["opener_rate"].fillna(df["label"].mean()).to_numpy()
    return team.assign(
        team_opened=opened,
        actual=np.where(opened, team["label"], 1 - team["label"]),
        expected=np.where(opened, rate, 1 - rate),
        team_side=np.where(opened, team["opener_side"], team["other_side"]),
        team_agent=np.where(opened, team.get("opener_agent", pd.Series(index=team.index, dtype=object)),
                            team.get("other_agent", pd.Series(index=team.index, dtype=object))),
    )


def section(g: pd.DataFrame) -> dict:
    if g.empty:
        return dict(n=0, actual=None, expected=None, diff=None, lo=None, hi=None, beyond_noise=False, p_value=None)
    vals = (g["actual"] - g["expected"]).astype(float)
    lo, hi = bootstrap_mean(vals.tolist(), g["series_id"].astype(str).tolist(), n=1000, seed=42)
    p = mean_p(float(vals.mean()), lo, hi, g["series_id"].nunique())   # None with one series: no range, no finding
    return dict(n=int(len(g)), actual=round(float(g["actual"].mean()), 4), expected=round(float(g["expected"].mean()), 4),
                diff=round(float(vals.mean()), 4), lo=round(float(lo), 4), hi=round(float(hi), 4),
                beyond_noise=bool(p is not None and (lo > 0 or hi < 0)), p_value=p)


@metric(DRY_DUELS)
def dry_duels(con, f: Filters) -> MetricResult:
    res = MetricResult(DRY_DUELS, f)
    path = Path(FIGHTS_PARQUET)
    if not path.exists():
        res.warnings.append("Run python -m engine.model.fights first")
        return res
    df, rates = _load(str(path), path.stat().st_mtime)
    team = team_view(df, rates, str(f.team_id))
    if f.map:
        team = team[team["map"] == f.map]
    if f.side:
        team = team[team["team_side"] == f.side]
    if f.since or f.until:
        res.warnings.append("Dry duels ignore the date filter.")
    if team.empty:
        return res

    res.value = dict(total=int(len(team)), **section(team))
    res.breakdown = [
        dict(bucket="opened", label="They opened", **section(team[team["team_opened"]])),
        dict(bucket="enemy_opened", label="The enemy opened", **section(team[~team["team_opened"]])),
    ]
    for agent, g in team.groupby("team_agent"):
        if isinstance(agent, str) and agent and len(g) >= MIN_AGENT_FIGHTS:
            res.breakdown.append(dict(bucket="agent", agent=agent, **section(g)))
    # naming one agent out of several is a multiple comparison (D-024)
    agents = [b for b in res.breakdown if b["bucket"] == "agent"]
    for b, kept in zip(agents, benjamini_hochberg([b["p_value"] for b in agents])):
        b["survives"] = bool(kept and b["beyond_noise"])
    res.supporting = sorted(set(team.loc[team["actual"] == 1, "round_key"].astype(str)))
    res.contrary = sorted(set(team.loc[team["actual"] == 0, "round_key"].astype(str)))
    res.series = int(team["series_id"].nunique())
    res.maps = int(team["map"].nunique())
    return res
