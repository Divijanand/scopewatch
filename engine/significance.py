"""Which differences from the league are worth reporting (D-024).

A report runs dozens of checks, so some look unusual by luck. Two corrections:
  1. Rounds in one series aren't independent (a team's plan is partly set per series). Each rate's standard error is
     inflated by the league-wide dispersion of that measure (`DISPERSION`, measured by scripts/eval_findings.py).
  2. Benjamini-Hochberg across every check in the report, including the ones that don't stand out, aims to keep the
     expected share of false findings at or below Q.
"""
from __future__ import annotations

import math

from scipy import stats

Q = 0.10

# Pearson dispersion across series within one team, map and side; 1 = rounds are independent.
DISPERSION = {
    "att.executes": 1.06,
    "util.recon_timing.before": 2.37,
    "util.recon_timing.late": 1.36,
    "team.retakes.retake": 1.44,
    "team.retakes.plants_faced": 1.69,
    "team.post_plant.win": 1.45,
    "team.post_plant.pre_plant_losses": 1.12,
    "team.post_plant.plant_share": 1.66,
    "team.economy.full_vs_full": 1.36,
    "team.economy.full_vs_anti": 1.13,
    "team.economy.scrappy_vs_full": 1.18,
    "team.openings.first_blood": 1.26,
    "team.openings.after_first_blood": 1.38,
    "team.openings.after_first_death": 1.38,
    "team.economy.pistol": 1.0,      # at most one per map and side, so there is nothing to cluster
    "team.economy.bonus": 1.0,
}
UNMEASURED = max(DISPERSION.values())   # habits and closing rounds: assume the worst measured case


def dispersion(test_id: str) -> float:
    if test_id.startswith("att.executes."):
        return DISPERSION["att.executes"]
    return DISPERSION.get(test_id, UNMEASURED)


def _tail(z: float, direction: str, df: int | None = None) -> float:
    def sf(x):
        return stats.norm.sf(x) if df is None else stats.t.sf(x, df)
    if direction == "higher":
        return float(sf(z))
    if direction == "lower":
        return float(sf(-z))
    return float(min(1.0, 2 * sf(abs(z))))


def rate_p(r, league_p, phi: float = 1.0, direction: str = "both") -> float | None:
    """p-value of a Rate dict against a league rate. Only a direction fixed in advance may be one-sided."""
    if not r or r.get("p") is None or not r.get("n") or r.get("small_sample") or league_p is None:
        return None
    if not 0 < league_p < 1:
        return None
    se = math.sqrt(phi * league_p * (1 - league_p) / r["n"])
    return _tail((r["p"] - league_p) / se, direction)


def two_rates_p(a, b, phi: float = 1.0, direction: str = "both") -> float | None:
    """p-value of rate a against rate b (pooled). direction describes a compared with b."""
    if not a or not b or a.get("p") is None or b.get("p") is None or a.get("small_sample") or b.get("small_sample"):
        return None
    pool = (a["k"] + b["k"]) / (a["n"] + b["n"])
    if not 0 < pool < 1:
        return None
    se = math.sqrt(phi * pool * (1 - pool) * (1 / a["n"] + 1 / b["n"]))
    return _tail((a["p"] - b["p"]) / se, direction)


def mean_p(mean, lo, hi, groups: int, null: float = 0.0) -> float | None:
    """p-value of a mean from its 90% t interval (core.bootstrap_mean, method 't') over `groups` series.
    None for a single series: its range has no width because nothing can be estimated."""
    if mean is None or lo is None or hi is None or groups < 2 or hi <= lo:
        return None
    se = (hi - lo) / 2 / float(stats.t.ppf(0.95, groups - 1))
    return _tail((mean - null) / se, "both", groups - 1)


def benjamini_hochberg(ps: list[float | None], q: float = Q) -> list[bool]:
    """Which p-values are kept. None means the check could not be run: it is never kept and not counted."""
    real = sorted((p, i) for i, p in enumerate(ps) if p is not None)
    cut = 0
    for rank, (p, _) in enumerate(real, 1):
        if p <= q * rank / len(real):
            cut = rank
    keep = {i for _, i in real[:cut]}
    return [i in keep for i in range(len(ps))]
