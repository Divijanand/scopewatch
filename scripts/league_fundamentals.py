"""Step 5c: league-level fundamentals by map (no team names or ids: safe for docs/).

    python -m scripts.league_fundamentals

Retakes and post-plant wins by numbers at the plant, buy matchups, pistol and bonus rounds, first-blood
conversion, comebacks and throws. Ranges are 90% series-bootstrap t intervals (D-020): rounds in one series
aren't independent.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np

from engine.config import DB_PATH, ROOT
from engine.metrics import fundamentals as fm
from engine.metrics.core import Filters, bootstrap_mean

MIN_N = 50


def rate(rows, won) -> str:
    """Win rate over `rows` (round rows from fundamentals' rounds query) with its series range."""
    if len(rows) < MIN_N:
        return "–"
    vals = [1.0 if won(r) else 0.0 for r in rows]
    lo, hi = bootstrap_mean(vals, [str(r[1]) for r in rows], n=1000, seed=42)
    return f"{np.mean(vals):.1%} [{lo:.1%}, {hi:.1%}] (n={len(rows):,})"


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    maps = [m for (m,) in con.execute("SELECT DISTINCT map FROM team_rounds ORDER BY 1").fetchall()]
    sections = {k: [] for k in ("plant", "eco", "open", "close")}
    extremes = fm._round_extremes(con) if Path(fm.EVENT_WP_PARQUET).exists() else None
    for m in maps:
        att = fm._league_rounds(con, Filters(team_id="", map=m, side="attacker"))
        dfn = fm._league_rounds(con, Filters(team_id="", map=m, side="defender"))
        both = att + dfn
        planted = [r for r in att if r[9]]
        alive = fm._plant_alive(con, planted)
        by = {b: [r for r in planted if alive.get(r[0], {}).get("bucket") == b] for b in fm.PLANT_BUCKETS}
        sections["plant"].append(f"| {m} | {rate(att, lambda r: r[9])} | {rate(planted, lambda r: r[5])} "
                                 f"| {rate(by['ahead'], lambda r: r[5])} | {rate(by['even'], lambda r: r[5])} "
                                 f"| {rate(by['behind'], lambda r: r[5])} |")

        known = [r for r in att if r[7] is not None and r[13] is not None]   # both sides would be 50% by construction
        pistols = [r for r in known if fm._is_pistol(r[3])]
        pwin = {(fm._game(r[0]), r[3], r[6]): r[5] for r in pistols}
        bonus = [r for r in known if r[3] in (2, 14) and pwin.get((fm._game(r[0]), r[3] - 1, r[6]))]
        cells = []
        for _, own, opp in fm.ECO_BUCKETS:
            rs = [r for r in known if r[7] in fm.OWN[own] and r[13] in opp and not fm._is_pistol(r[3])]
            cells.append(rate(rs, lambda r: r[5]))
        sections["eco"].append(f"| {m} | {' | '.join(cells)} | {rate(pistols, lambda r: r[5])} "
                               f"| {rate(bonus, lambda r: r[5])} |")

        fb = fm._first_blood(con, list({r[0] for r in both}))
        got = [r for r in both if r[0] in fb and fb[r[0]]["att_team"] == r[6]]
        got_att = [r for r in got if r[4] == "attacker"]
        got_def = [r for r in got if r[4] == "defender"]
        sections["open"].append(f"| {m} | {rate(got, lambda r: r[5])} | {rate(got_att, lambda r: r[5])} "
                                f"| {rate(got_def, lambda r: r[5])} |")

        if extremes is not None:
            e = extremes[extremes["map"] == m]
            cb = e[e["min_wp"] <= 0.2]
            cbr = rate(list(zip(cb["round_key"], cb["series_id"], cb["won"])), lambda r: r[2])
            sections["close"].append(f"| {m} | {cbr} |")
    con.close()

    lines = [
        "# League fundamentals by map",
        "",
        f"Run {datetime.now().isoformat(timespec='seconds')} on all series. League-level only. "
        "Each cell: rate [90% series-bootstrap range] (n). Cells with fewer than 50 rounds are left blank (–).",
        "",
        "## Plants and post-plant (attack rounds)",
        "",
        "Numbers at the plant from the attackers' view, from kills and revives at or before the plant.",
        "",
        "| Map | Attack rounds with a plant | Attackers win after planting | ... up a player or more | ... even | ... down a player or more |",
        "|---|---|---|---|---|---|",
        *sections["plant"],
        "",
        "## Economy (attackers' win rate)",
        "",
        "From the attackers' side: counted over both sides, pistols and full-against-full would be 50% by "
        "construction. Buy matchups leave out pistol rounds. Bonus = rounds 2 and 14 after the same team won the pistol.",
        "",
        "| Map | Full against full | Full against eco or half | Eco or half against full | Pistol | Bonus after a pistol win |",
        "|---|---|---|---|---|---|",
        *sections["eco"],
        "",
        "## First blood (round win rate after getting first blood)",
        "",
        "| Map | Both sides | On attack | On defence |",
        "|---|---|---|---|",
        *sections["open"],
    ]
    if sections["close"]:
        lines += [
            "",
            "## Comebacks and throws",
            "",
            "Per round and side, from the win-probability model after every kill and plant. Comeback = won after "
            "falling to 20% or lower; throw = lost after reaching 80% or higher. League-wide the two are the same "
            "rounds seen from each side (one team's comeback is the other's throw), so the throw rate equals the "
            "comeback rate by construction; per team they differ, which is what the team card shows.",
            "",
            "| Map | Comebacks (= throws, league-wide) |",
            "|---|---|",
            *sections["close"],
        ]
    out = ROOT / "docs" / "LEAGUE_FUNDAMENTALS.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out}: {len(maps)} maps")


if __name__ == "__main__":
    main()
