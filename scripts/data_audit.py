"""Step 2 of docs/ROADMAP_ML.md: what happens, how often, and where the data is thin.

    python -m scripts.data_audit

Writes docs/DATA_AUDIT.md with corpus-wide aggregates only (counts and rates, never rows).
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date

import duckdb
import numpy as np

from engine.config import DB_PATH, ROOT
from engine.model import winprob
from engine.roles import ROLE

THIN = 200          # fewer training states than this in a game state = thin for T1


def pct(k, n):
    return f"{100 * k / n:.1f}%" if n else "–"


def main():
    con = duckdb.connect(DB_PATH.as_posix(), read_only=True)
    q = lambda sql, *a: con.execute(sql, list(a)).fetchall()  # noqa: E731
    out = [f"# Data audit (step 2)", "",
           f"Run {date.today()} with `python -m scripts.data_audit` on the full store. Aggregates only. "
           "What happens, how often, and where the data is too thin for a model to learn.", ""]

    # ---------------------------------------------------------------- corpus and ingest health
    (series, games, rounds), = q("SELECT count(DISTINCT series_id), count(DISTINCT game_id), count(*) FROM rounds")
    counts = Counter()
    for (cj,) in q("SELECT counts_json FROM manifest WHERE status = 'ok'"):
        for k, v in (json.loads(cj) if cj else {}).items():
            if isinstance(v, (int, float)):
                counts[k] += v
    out += ["## 1. Corpus and ingest health", "",
            f"- {series:,} series, {games:,} games, {rounds:,} rounds.",
            f"- Reversals undone during ingest: {int(counts.get('reversals_lifo', 0)):,} "
            f"(non-LIFO {int(counts.get('reversals_non_lifo', 0)):,}, unmatched {int(counts.get('reversals_unmatched', 0)):,}).",
            f"- Kills still without a weapon after the backfill: "
            f"{q('SELECT count(*) FROM engagements WHERE kind = ? AND weapon IS NULL', 'kill')[0][0]:,}.", ""]

    # ---------------------------------------------------------------- T1 game states: what's common, what's thin
    df = winprob.get_training_data()
    states = df.groupby(["attackers_alive", "defenders_alive", "planted"]).agg(
        n=("label", "size"), att_win=("label", "mean")).reset_index()
    thin = states[states["n"] < THIN].sort_values("n")
    out += ["## 2. Game states the win-probability model sees (T1)", "",
            f"{len(df):,} training states (after each kill and plant) in {df['series_id'].nunique():,} series, "
            f"{len(states)} distinct (attackers alive, defenders alive, planted) states.", "",
            "| State | States | Attackers win |", "|---|---|---|"]
    for label, a, d, p in [("5v5, no plant", 5, 5, False), ("4v5 (first kill to defense)", 4, 5, False),
                           ("5v4 (first kill to attack)", 5, 4, False), ("1v1, no plant", 1, 1, False),
                           ("1v1, planted", 1, 1, True), ("2v1, planted", 2, 1, True), ("1v2, planted", 1, 2, True),
                           ("1v3, planted (attacker clutch)", 1, 3, True), ("4v1, no plant", 4, 1, False),
                           ("1v4, no plant", 1, 4, False), ("1v5, planted", 1, 5, True)]:
        r = states[(states.attackers_alive == a) & (states.defenders_alive == d) & (states.planted == p)]
        if len(r):
            out.append(f"| {label} | {int(r.n.iloc[0]):,} | {r.att_win.iloc[0]:.1%} |")
    out += ["", f"**Thin states** (fewer than {THIN} training states): {len(thin)} of {len(states)}, "
            f"covering {int(thin.n.sum()):,} states ({pct(int(thin.n.sum()), len(df))} of all). "
            "These are where model ranges must be widest, and where synthetic stress tests are useful.", "",
            "| Attackers | Defenders | Planted | States | Attackers win |", "|---|---|---|---|---|"]
    for r in thin.head(12).itertuples():
        out.append(f"| {r.attackers_alive} | {r.defenders_alive} | {'yes' if r.planted else 'no'} | {r.n} | {r.att_win:.1%} |")
    neg = df[(df.attackers_alive < 0) | (df.defenders_alive < 0)]
    out += ["", f"States with a negative alive count (more deaths than players, a data error): {len(neg):,}.", ""]

    # ---------------------------------------------------------------- economy matchups
    rows = q("""SELECT a.economy, d.economy, count(*), avg((r.winner_side = 'attacker')::INT)
                FROM rounds r
                JOIN team_rounds a ON a.round_key = r.round_key AND a.side = 'attacker'
                JOIN team_rounds d ON d.round_key = r.round_key AND d.side = 'defender'
                WHERE a.inventory_known AND d.inventory_known GROUP BY 1, 2 ORDER BY 3 DESC""")
    out += ["## 3. Economy matchups (T4 and every model's prior)", "",
            "| Attack | Defense | Rounds | Attackers win |", "|---|---|---|---|"]
    out += [f"| {a} | {d} | {n:,} | {w:.1%} |" for a, d, n, w in rows]
    out += ["", "Eco-vs-full rounds are rare and lopsided: the model learns them from few examples.", ""]

    # ---------------------------------------------------------------- drift by patch
    rows = q("""SELECT g.patch, count(*) n, avg((r.winner_side = 'attacker')::INT) att,
                       avg(r.planted::INT) planted
                FROM rounds r JOIN games g USING (game_id) GROUP BY 1 ORDER BY min(g.started_at)""")
    ops = dict(q("""SELECT patch, avg((n_op > 0)::INT) FROM team_rounds WHERE inventory_known AND economy = 'full'
                    GROUP BY 1"""))
    out += ["## 4. Drift by patch", "",
            "| Patch | Rounds | Attackers win | Planted | Full buys with an Operator |", "|---|---|---|---|---|"]
    for patch, n, att, planted in rows:
        out.append(f"| {patch} | {n:,} | {att:.1%} | {planted:.1%} | {ops.get(patch, 0):.1%} |")
    att = [r[2] for r in rows if r[1] >= 500]
    out += ["", f"Across patches with at least 500 rounds, the attacker win rate ranges from {min(att):.1%} to "
            f"{max(att):.1%}. A model trained on all patches averages over that; the patch-forward check "
            "(ML_TAXONOMY.md section 5) measures what drift costs.", ""]

    # ---------------------------------------------------------------- agents and comps over time
    picks = q("""SELECT g.patch, p.agent, count(DISTINCT p.round_key || p.player_id) n
                 FROM player_rounds p JOIN games g USING (game_id) WHERE p.agent IS NOT NULL GROUP BY 1, 2""")
    by_patch = {}
    for patch, agent, n in picks:
        by_patch.setdefault(patch, Counter())[agent] = n
    agents = Counter()
    for c in by_patch.values():
        agents.update(c)
    ordered = [p for p, *_ in rows]
    out += ["## 5. Agents and roles", "",
            "| Agent | Role | Player rounds | Share in first patch → last patch with data |", "|---|---|---|---|"]
    for agent, n in agents.most_common():
        shares = [by_patch[p].get(agent, 0) / max(1, sum(by_patch[p].values())) for p in ordered if p in by_patch]
        nz = [s for s in shares if s > 0]
        trend = f"{nz[0]:.1%} → {nz[-1]:.1%}" if nz else "–"
        out.append(f"| {agent} | {ROLE.get(agent, '?')} | {n:,} | {trend} |")
    comps = q("""SELECT count(*), count(DISTINCT comp) FROM (SELECT game_id, team_id,
                 list(DISTINCT agent ORDER BY agent) comp FROM player_rounds WHERE agent IS NOT NULL GROUP BY 1, 2)""")[0]
    out += ["", f"{comps[1]:,} distinct team comps across {comps[0]:,} team-games: most comps are seen once or twice, "
            "so a model should use roles and agent embeddings, not one comp = one category.", ""]

    # ---------------------------------------------------------------- utility data quality
    (casts, ok, low), = q("SELECT count(*), avg(spatial_ok::INT), avg(low_rate::INT) FROM casts")
    by_event = q("""SELECT event, count(*), avg(low_rate::INT) FROM casts GROUP BY 1 HAVING avg(low_rate::INT) > 0.2
                    ORDER BY 3 DESC""")
    out += ["## 6. Utility data quality", "",
            f"- {casts:,} casts; {ok:.1%} have a usable position; {low:.1%} come from about 1 Hz position sampling.",
            "- Events where more than 20% of casts are low-rate:"]
    out += [f"  - {e}: {n:,} casts, {lr:.0%} low-rate" for e, n, lr in by_event[:8]]
    out += ["", "A position-based utility feature must carry the low-rate flag, or be dropped for those events.", ""]

    # ---------------------------------------------------------------- what each task can and can't learn
    (n_sites,), = q("SELECT count(*) FROM objectives WHERE kind = 'plant'")
    (team_maps_small,), = q("""SELECT count(*) FROM (SELECT team_id, map, count(*) n FROM team_rounds
                               WHERE side = 'attacker' GROUP BY 1, 2) WHERE n < 24""")
    (team_maps,), = q("SELECT count(*) FROM (SELECT DISTINCT team_id, map FROM team_rounds WHERE side = 'attacker')")
    out += ["## 7. What this means for each task", "",
            f"- **T1 win probability:** {len(df):,} states is plenty for gradient boosting and a small sequence model. "
            f"The risk is the {len(thin)} thin states, not the total.",
            f"- **T2 next-round site:** {n_sites:,} plants, but per team and map the data is small: "
            f"{team_maps_small:,} of {team_maps:,} (team, map) pairs have fewer than 24 attack rounds (two halves). "
            "Team habits must be pooled toward the league (shrinkage), and the baseline to beat is "
            "\"always their most common site\".",
            "- **T3 Operator buy:** depends on economy and on who's on the team. A roster change resets a team's habits, "
            "so recent rounds should count for more.",
            "- **All tasks:** split by series; check patch-forward; report thin-state performance separately.", ""]

    (ROOT / "docs" / "DATA_AUDIT.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote docs/DATA_AUDIT.md ({len(out)} lines)")


if __name__ == "__main__":
    main()
