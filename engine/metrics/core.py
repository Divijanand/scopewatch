"""Metric contracts: definitions, filters, rates and results.

Every displayed rate resolves to: definition (id + version), population rule, numerator and
denominator, unknown/excluded counts with reasons, independent maps and series, an interval,
and the round keys behind it (supporting and contrary). See docs/METRICS.md.
"""
from __future__ import annotations

import hashlib
import json
import math
import numpy as np
from dataclasses import asdict, dataclass, field

Z95 = 1.96
SMALL_SAMPLE = 10

def bootstrap_mean(values: list[float], groups: list[str], n=1000, seed=0, method: str = "t") -> tuple[float, float]:
    """90% interval (lo, hi) of the mean, resampling whole groups (series) with replacement.

    method="t" (default): mean ± t(0.95, G-1) × bootstrap SE × sqrt(G/(G-1)), with G = number of groups.
        On clustered data with a known truth it covers 90–91.5% from 4 to 60 groups (docs/EVAL_BOOTSTRAP.md);
        the plain percentile interval falls to 81% at 6 groups and 75% at 4.
    method="percentile": the 5th–95th percentile of the resampled means (kept for comparison).
    With a single group nothing can be estimated, and (mean, mean) is returned: callers must not show it as a range.
    Resamples are drawn as one array; each replicate's mean comes from per-group sums and counts.
    """
    if not values:
        return 0.0, 0.0
    rng = np.random.default_rng(seed)
    unique_groups = sorted(set(groups))
    m = float(np.mean(values))
    if len(unique_groups) < 2:
        return m, m
    gi = {g: i for i, g in enumerate(unique_groups)}
    idx = np.fromiter((gi[g] for g in groups), dtype=np.int64, count=len(groups))
    v = np.asarray(values, dtype=float)
    sums = np.bincount(idx, weights=v, minlength=len(unique_groups))
    counts = np.bincount(idx, minlength=len(unique_groups)).astype(float)
    draws = rng.choice(len(unique_groups), size=(n, len(unique_groups)), replace=True)
    means = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    if method == "percentile":
        return float(np.percentile(means, 5)), float(np.percentile(means, 95))
    g = len(unique_groups)
    half = _student_t_95(g - 1) * float(means.std(ddof=1)) * float(np.sqrt(g / (g - 1)))
    return m - half, m + half


def _student_t_95(df: int) -> float:
    """95th percentile of Student's t with df degrees of freedom (one side of a 90% interval)."""
    from scipy import stats
    return float(stats.t.ppf(0.95, df))


def ranked(counter, n=None):
    """Counter.most_common with ties broken by name, so the same data always ranks the same way."""
    items = sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))
    return items if n is None else items[:n]


@dataclass(frozen=True)
class MetricDef:
    id: str
    version: int
    title: str
    question: str
    population: str
    numerator: str
    unit: str
    caveats: tuple[str, ...] = ()


@dataclass
class Rate:
    k: int
    n: int
    p: float | None = None
    lo: float | None = None
    hi: float | None = None
    small_sample: bool = False

    @classmethod
    def of(cls, k: int, n: int) -> "Rate":
        if n == 0:
            return cls(k=0, n=0, small_sample=True)
        p = k / n
        d = 1 + Z95 ** 2 / n
        c = (p + Z95 ** 2 / (2 * n)) / d
        h = Z95 * math.sqrt(p * (1 - p) / n + Z95 ** 2 / (4 * n * n)) / d
        return cls(k=k, n=n, p=round(p, 4), lo=round(max(0.0, c - h), 4), hi=round(min(1.0, c + h), 4),
                   small_sample=n < SMALL_SAMPLE)


@dataclass
class Filters:
    team_id: str
    map: str | None = None
    side: str | None = None          # attacker | defender
    since: str | None = None         # ISO date, inclusive
    until: str | None = None         # ISO date, exclusive
    player_id: str | None = None

    def hash(self) -> str:
        return hashlib.sha1(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:12]

    def where(self, alias: str, team_col="team_id", side_col="side", map_col="map", date_col="started_at"):
        a = f"{alias}." if alias else ""
        w, p = [f"{a}{team_col} = ?"], [self.team_id]
        if self.map:
            w.append(f"{a}{map_col} = ?"); p.append(self.map)
        if self.side:
            w.append(f"{a}{side_col} = ?"); p.append(self.side)
        if self.since:
            w.append(f"{a}{date_col} >= ?::TIMESTAMP"); p.append(self.since)
        if self.until:
            w.append(f"{a}{date_col} < ?::TIMESTAMP"); p.append(self.until)
        return " AND ".join(w), p


@dataclass
class Unknown:
    count: int
    reason: str


@dataclass
class MetricResult:
    metric: MetricDef
    filters: Filters
    rate: Rate | None = None
    breakdown: list[dict] = field(default_factory=list)  # e.g. per player / per time bucket
    value: dict = field(default_factory=dict)            # non-rate results (medians etc.)
    unknown: list[Unknown] = field(default_factory=list)
    maps: int = 0
    series: int = 0
    supporting: list[str] = field(default_factory=list)  # round keys
    contrary: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self, evidence_limit: int | None = 50):
        d = asdict(self)
        d["metric_id"] = f"{self.metric.id}@v{self.metric.version}"
        d["evidence_counts"] = dict(supporting=len(self.supporting), contrary=len(self.contrary))
        if evidence_limit is not None:
            d["supporting"] = self.supporting[:evidence_limit]
            d["contrary"] = self.contrary[:evidence_limit]
        return d


REGISTRY: dict[str, tuple[MetricDef, callable]] = {}


def metric(defn: MetricDef):
    def deco(fn):
        REGISTRY[defn.id] = (defn, fn)
        return fn
    return deco
