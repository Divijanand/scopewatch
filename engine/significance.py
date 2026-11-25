"""Which differences from the league are worth reporting (D-024).

A report runs dozens of checks, so some look unusual by luck. Two corrections:
  1. Rounds in one game aren't independent. Each rate carries its design effect (`deff`, engine/clustering.py), the
     same one its printed range uses, and its standard error is inflated by it.
  2. Benjamini-Hochberg across every check in the report, including the ones that don't stand out, aims to keep the
     expected share of false findings at or below Q.
"""
from __future__ import annotations

import math

from scipy import stats

Q = 0.10

def _tail(z: float, direction: str, df: int | None = None) -> float:
    def sf(x):
        return stats.norm.sf(x) if df is None else stats.t.sf(x, df)
    if direction == "higher":
        return float(sf(z))
    if direction == "lower":
        return float(sf(-z))
    return float(min(1.0, 2 * sf(abs(z))))


def rate_p(r, league_p, direction: str = "both") -> float | None:
    """p-value of a Rate dict against a league rate. Only a direction fixed in advance may be one-sided."""
    if not r or r.get("p") is None or not r.get("n") or r.get("small_sample") or league_p is None:
        return None
    if not 0 < league_p < 1:
        return None
    se = math.sqrt(r.get("deff", 1.0) * league_p * (1 - league_p) / r["n"])
    return _tail((r["p"] - league_p) / se, direction)


def two_rates_p(a, b, direction: str = "both") -> float | None:
    """p-value of rate a against rate b (pooled). direction describes a compared with b."""
    if not a or not b or a.get("p") is None or b.get("p") is None or a.get("small_sample") or b.get("small_sample"):
        return None
    pool = (a["k"] + b["k"]) / (a["n"] + b["n"])
    if not 0 < pool < 1:
        return None
    se = math.sqrt(pool * (1 - pool) * (a.get("deff", 1.0) / a["n"] + b.get("deff", 1.0) / b["n"]))
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
