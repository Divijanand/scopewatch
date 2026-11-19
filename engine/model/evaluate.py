"""How every model on the deep-learning branch is measured (docs/ML_TAXONOMY.md section 3).

A probability model is judged on its probabilities: is it honest (calibration), is it sharp (log loss,
Brier, AUC), does it beat the obvious guess (baseline), and is a win over another model real (paired
bootstrap over whole series)? Ranges shown in the product are judged on coverage (accuracy) and width
(precision).
"""
from __future__ import annotations

from collections import Counter

import numpy as np

EPS = 1e-15


# ------------------------------------------------------------------ binary probabilities (T1, T3, T4)
def log_loss(y, p) -> float:
    """Mean negative log likelihood; lower is better. 0.693 = a coin flip."""
    y = np.asarray(y, float)
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(y, p) -> float:
    """Mean squared error of the probability; lower is better. 0.25 = always saying 50%."""
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    return float(np.mean((p - y) ** 2))


def auc(y, p) -> float | None:
    """Probability that a random win is scored above a random loss (ties count half). None if one class."""
    y = np.asarray(y, int)
    p = np.asarray(p, float)
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order), float)
    allp = np.concatenate([pos, neg])[order]
    # average ranks for ties
    i = 0
    while i < len(allp):
        j = i
        while j + 1 < len(allp) and allp[j + 1] == allp[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    rank_pos = ranks[:len(pos)].sum()
    return float((rank_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def calibration(y, p, bins: int = 10) -> dict:
    """Reliability table (per bin: mean predicted, actual rate, count) and expected calibration error:
    the count-weighted mean gap between predicted and actual. 0 = perfectly honest probabilities."""
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    table, ece = [], 0.0
    for b in range(bins):
        m = idx == b
        n = int(m.sum())
        if n:
            mp, act = float(p[m].mean()), float(y[m].mean())
            ece += n / len(p) * abs(mp - act)
            table.append(dict(lo=float(edges[b]), hi=float(edges[b + 1]), predicted=mp, actual=act, n=n))
        else:
            table.append(dict(lo=float(edges[b]), hi=float(edges[b + 1]), predicted=None, actual=None, n=0))
    return dict(ece=float(ece), table=table)


def evaluate_binary(y, p) -> dict:
    cal = calibration(y, p)
    return dict(n=int(len(y)), log_loss=log_loss(y, p), brier=brier(y, p), auc=auc(y, p), ece=cal["ece"],
                reliability=cal["table"])


# ------------------------------------------------------------------ multiclass choices (T2, T5)
def multiclass_log_loss(y, probs: list[dict]) -> float:
    """y: true labels; probs: one {label: probability} per row (missing labels count as 0)."""
    return float(-np.mean([np.log(max(pr.get(t, 0.0), EPS)) for t, pr in zip(y, probs)]))


def top1(y, probs: list[dict]) -> float:
    """Share of rows where the most likely label (ties broken by name) is the true one."""
    hits = [max(sorted(pr), key=lambda k: pr[k]) == t for t, pr in zip(y, probs) if pr]
    return float(np.mean(hits)) if hits else 0.0


def baseline_most_common(train_y, train_groups, test_groups, smoothing: float = 1.0):
    """The obvious guess: each group's (e.g. team's) label frequencies from training, Laplace-smoothed over
    all labels seen in training; unseen groups get the overall frequencies."""
    labels = sorted(set(train_y))
    overall = Counter(train_y)
    by_group = {}
    for t, g in zip(train_y, train_groups):
        by_group.setdefault(g, Counter())[t] += 1

    def dist(c: Counter):
        total = sum(c.values()) + smoothing * len(labels)
        return {lab: (c.get(lab, 0) + smoothing) / total for lab in labels}

    overall_d = dist(overall)
    return [dist(by_group[g]) if g in by_group else overall_d for g in test_groups]


# ------------------------------------------------------------------ is B really better than A?
def paired_difference(y, p_a, p_b, groups, metric=log_loss, n: int = 1000, seed: int = 0) -> dict:
    """metric(B) - metric(A) on the same rows, with a 90% range from resampling whole groups (series).
    For log loss, a range entirely below 0 means B is better beyond noise."""
    y, p_a, p_b = np.asarray(y, float), np.asarray(p_a, float), np.asarray(p_b, float)
    groups = np.asarray(groups)
    ug = np.array(sorted(set(groups.tolist())))
    members = {g: np.nonzero(groups == g)[0] for g in ug}
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n):
        pick = rng.choice(len(ug), size=len(ug), replace=True)
        idx = np.concatenate([members[ug[i]] for i in pick])
        diffs.append(metric(y[idx], p_b[idx]) - metric(y[idx], p_a[idx]))
    point = metric(y, p_b) - metric(y, p_a)
    lo, hi = np.percentile(diffs, [5, 95])
    return dict(difference=float(point), lo=float(lo), hi=float(hi),
                b_better=bool(hi < 0) if metric in (log_loss, brier) else bool(lo > 0))


# ------------------------------------------------------------------ are our ranges honest?
def coverage(intervals, truths) -> dict:
    """intervals: (lo, hi) pairs; truths: the value each range should contain.
    coverage = share containing the truth (accuracy of the ranges); width = mean hi - lo (precision)."""
    iv = np.asarray(intervals, float)
    t = np.asarray(truths, float)
    inside = (iv[:, 0] <= t) & (t <= iv[:, 1])
    return dict(n=int(len(t)), coverage=float(inside.mean()), mean_width=float((iv[:, 1] - iv[:, 0]).mean()))
