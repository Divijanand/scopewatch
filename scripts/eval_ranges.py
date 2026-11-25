"""Are the ranges on the cards wide enough? (D-025). League-level only: no team names or numbers, safe for docs/.

    python -m scripts.eval_ranges

1. Correlation: how much the rounds of one game repeat each other, per measure. Feeds engine/clustering.py (RHO).
2. Check: split a team's games into two random halves. Both halves estimate the same thing, so their rates should
   differ by more than the 95% allowance in 5% of cases. Old ranges (independent rounds) against new ones, with the
   correlation measured on half of the teams and the check run on the other half.
"""
from __future__ import annotations

import collections
import logging
import math
from datetime import datetime

import duckdb
import numpy as np

from engine import clustering
from engine.config import DB_PATH, ROOT
from engine.metrics import REGISTRY, Filters
from engine.metrics.utility import agent_rounds

MIN_GAMES = 5           # games in a team-map-side (or team-map)
MIN_SPLIT_GAMES = 6     # games needed to split in two
MIN_EXPECTED = 5        # hits and misses expected in each half, so the z statistic is meaningful
MIN_RATES = 40          # rates needed before a measure gets its own correlation
MIN_AGENT_ROUNDS = 60   # an agent's own rounds, for the one-agent utility view
SPLITS = 4
UTIL_GROUPS = ("setup", "damage", "smoke", "flash", "recon")


def collect(con, both_sides=False):
    """{(team, map, side): [(measure, {game: (k, n)})]} for every clustered rate the metrics build."""
    side = "NULL" if both_sides else "side"
    combos = con.execute(f"SELECT team_id, map, {side} FROM team_rounds GROUP BY ALL HAVING count(DISTINCT game_id) >= ? "
                         "ORDER BY ALL", [MIN_GAMES]).fetchall()
    out = {}
    try:
        for t, m, s in combos:
            clustering.RECORD = []
            f = Filters(team_id=t, map=m, side=s)
            for mid, (_, fn) in REGISTRY.items():
                if mid == "util.placements":
                    for g in UTIL_GROUPS:
                        fn(con, f, group=g)
                    if s:
                        for a, rks in agent_rounds(con, f).items():
                            if len(rks) >= MIN_AGENT_ROUNDS:
                                fn(con, f, agent=a)
                else:
                    fn(con, f)
            seen, keep = set(), []
            for name, games in clustering.RECORD:      # a headline repeats its own breakdown row: count it once
                sig = (name, tuple(sorted(games.items())))
                if games and sig not in seen:
                    seen.add(sig)
                    keep.append((name, games))
            out[(t, m, s)] = keep
    finally:
        clustering.RECORD = None
    return out


def estimate_rho(data):
    """Moment estimator from the Pearson statistic: sum X2 = sum over games of (1 - m/n)(1 + (m - 1) rho), with the
    n / (n - 1) that keeps independent rounds at exactly 0."""
    num, den, cnt = collections.Counter(), collections.Counter(), collections.Counter()
    for rates in data.values():
        for name, games in rates:
            k, n = (sum(x[i] for x in games.values()) for i in (0, 1))
            if len(games) < MIN_GAMES or min(k, n - k) < MIN_EXPECTED:
                continue
            p = k / n
            x2 = sum((a - m * p) ** 2 / (m * p * (1 - p)) for a, m in games.values())
            num[name] += x2 - (len(games) - 1) * n / (n - 1)
            den[name] += sum((m - 1) * (1 - m / n) for _, m in games.values())
            cnt[name] += 1
    return {m: (num[m] / den[m], cnt[m]) for m in cnt if den[m] > 0 and cnt[m] >= MIN_RATES}


def _deff(sizes, rho):
    n = sum(sizes)
    return 1 + (sum(s * s for s in sizes) / n - 1) * rho


def split_check(data, rho_of, rng):
    """Per measure: how often two halves of the same team's games differ beyond 95%, with rho 0 and with rho_of."""
    out = collections.defaultdict(lambda: [0, 0, 0])
    for rates in data.values():
        for name, games in rates:
            if len(games) < MIN_SPLIT_GAMES:
                continue
            gs = list(games.values())
            for _ in range(SPLITS):
                perm = rng.permutation(len(gs))
                a, b = [gs[i] for i in perm[:len(gs) // 2]], [gs[i] for i in perm[len(gs) // 2:]]
                (ka, na), (kb, nb) = ((sum(x[0] for x in h), sum(x[1] for x in h)) for h in (a, b))
                p = (ka + kb) / (na + nb)
                if min(na, nb) * min(p, 1 - p) < MIN_EXPECTED:
                    continue
                gap = abs(ka / na - kb / nb) / math.sqrt(p * (1 - p))
                old = math.sqrt(1 / na + 1 / nb)
                r = rho_of(name)
                new = math.sqrt(_deff([x[1] for x in a], r) / na + _deff([x[1] for x in b], r) / nb)
                c = out[name]
                c[0] += 1
                c[1] += gap > 1.96 * old
                c[2] += gap > 1.96 * new
    return out


def total(check):
    n, o, w = (sum(c[i] for c in check.values()) for i in range(3))
    return n, o / n, w / n


def held_out(data, rng, default):
    """Correlation from half of the teams, check on the other half, both ways round."""
    teams = sorted({k[0] for k in data})
    side = dict(zip(teams, rng.permutation(len(teams)) % 2))
    out = collections.defaultdict(lambda: [0, 0, 0])
    for half in (0, 1):
        rho = estimate_rho({k: v for k, v in data.items() if side[k[0]] != half})
        res = split_check({k: v for k, v in data.items() if side[k[0]] == half},
                          lambda m: max(0.0, rho[m][0]) if m in rho else default, rng)
        for m, c in res.items():
            out[m] = [x + y for x, y in zip(out[m], c)]
    return out


def main():
    logging.disable(logging.WARNING)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    one, both = collect(con), collect(con, both_sides=True)
    con.close()
    rng = np.random.default_rng(11)
    rho = estimate_rho(one)
    default = float(np.percentile([max(0.0, v) for v, _ in rho.values()], 75))      # unmeasured: lean wide
    ho = held_out(one, rng, default)
    hb = split_check(both, lambda m: max(0.0, rho[m][0]) if m in rho else default, rng)
    wide = {}
    for rates in one.values():
        for name, games in rates:
            wide.setdefault(name, []).append(math.sqrt(_deff([m for _, m in games.values()], clustering.rho(name))))

    n1, o1, w1 = total(ho)
    n2, o2, w2 = total(hb)
    n3, o3, w3 = total({m: c for m, c in ho.items() if not m.startswith(("util.placements", "util.kit"))})
    lines = [
        "# Are the ranges wide enough?", "",
        f"Run {datetime.now().isoformat(timespec='seconds')}. League-level only. Method: D-025, `engine/clustering.py`.", "",
        "Rounds of one game repeat each other (same plan, same opponent, same day), so a range that treats them as "
        "independent is too narrow. Each team's games were split into two random halves: the halves estimate the same "
        "rate, so they should differ beyond the 95% allowance in 5% of cases.", "",
        "| Cards | Comparisons | Old ranges | New ranges |", "|---|---|---|---|",
        f"| One map, one side (correlation from other teams) | {n1:,} | {o1:.1%} | {w1:.1%} |",
        f"| The same, leaving out the utility spots (most of the comparisons) | {n3:,} | {o3:.1%} | {w3:.1%} |",
        f"| One map, both sides (correlation from the one-side cards) | {n2:,} | {o2:.1%} | {w2:.1%} |", "",
        "## Per measure", "",
        "Correlation: 0 means rounds of a game are independent. Wider: how much wider the typical one-side range is now. "
        "Disagreement: how often two halves differ beyond 95%, with the correlation taken from other teams (5% is right); "
        "measures with fewer than 200 comparisons are left out of it.", "",
        "| Measure | Correlation measured | In the code | Rates | Wider | Old disagreement | New disagreement |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in sorted(wide, key=lambda m: -(rho[m][0] if m in rho else -1)):
        c = ho.get(m, [0, 0, 0])
        lines.append("| `{}` | {} | {:.3f} | {} | {:.0%} | {} | {} |".format(
            m, f"{rho[m][0]:.3f}" if m in rho else "too few", clustering.rho(m), rho[m][1] if m in rho else len(wide[m]),
            float(np.median(wide[m])) - 1, *(f"{c[i] / c[0]:.1%}" if c[0] >= 200 else "–" for i in (1, 2))))
    lines += ["", f"Measures without enough rates use the 75th percentile, {default:.3f}. Negative correlations count as 0."]
    (ROOT / "docs" / "EVAL_RANGES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("\nRHO = {")
    for m, (v, _) in sorted(rho.items()):
        print(f'    "{m}": {max(0.0, v):.3f},')
    print(f"}}\nDEFAULT_RHO = {default:.3f}")


if __name__ == "__main__":
    main()
