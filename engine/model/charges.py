from __future__ import annotations

import pandas as pd

from engine.abilities import MODE


def merge_cast_uses(casts: pd.DataFrame) -> pd.DataFrame:
    """Merge repeated cast events from one ability use.

    Keeps the first cast for each (round_key, player_id, ability) streak where casts are <1.0s apart.
    """
    if casts.empty:
        return casts.copy()
    cols = ["round_key", "player_id", "ability", "t_round"]
    work = casts.sort_values(cols).copy()
    work["_prev_t"] = work.groupby(["round_key", "player_id", "ability"], sort=False)["t_round"].shift(1)
    keep = work["_prev_t"].isna() | ((work["t_round"] - work["_prev_t"]) >= 1.0)
    out = work.loc[keep].drop(columns=["_prev_t"]).reset_index(drop=True)
    return out


def estimate_charges(con) -> pd.DataFrame:
    """Estimate per-ability round charges from observed cast counts.

    Returns one row per (ability, agent) over player-rounds where that ability was cast at least once.
    """

    cast_cols = {r[1] for r in con.execute("PRAGMA table_info('casts')").fetchall()}
    has_cast_agent = "agent" in cast_cols
    has_cast_player = "player_id" in cast_cols
    if not has_cast_player:
        return pd.DataFrame(columns=[
            "ability", "agent", "typical_charges", "p50", "p95", "p99", "max",
            "share_above", "reusable", "n_player_rounds",
        ])
    if has_cast_agent:
        cast_rows = con.execute("""
            SELECT round_key, player_id, agent, ability, t_round
            FROM casts
            WHERE ability IS NOT NULL
              AND agent IS NOT NULL
              AND player_id IS NOT NULL
              AND phase IN ('buy', 'pre_plant', 'post_plant')
        """).df()
    else:
        cast_rows = con.execute("""
            SELECT c.round_key, c.player_id, pr.agent, c.ability, c.t_round
            FROM casts c
            LEFT JOIN player_rounds pr
              ON pr.round_key = c.round_key AND pr.player_id = c.player_id
            WHERE c.ability IS NOT NULL
              AND pr.agent IS NOT NULL
              AND c.player_id IS NOT NULL
              AND c.phase IN ('buy', 'pre_plant', 'post_plant')
        """).df()
    cast_rows = merge_cast_uses(cast_rows)

    counts = cast_rows.groupby(["agent", "ability", "round_key", "player_id"], sort=False).size().reset_index(name="casts")
    if counts.empty:
        return pd.DataFrame(columns=[
            "ability", "agent", "typical_charges", "p50", "p95", "p99", "max",
            "share_above", "reusable", "n_player_rounds",
        ])

    rows = []
    for (ability, agent), g in counts.groupby(["ability", "agent"], sort=False):
        p50 = int(g["casts"].quantile(0.50, interpolation="higher"))
        p95 = int(g["casts"].quantile(0.95, interpolation="higher"))
        p99 = int(g["casts"].quantile(0.99, interpolation="higher"))
        max_casts = int(g["casts"].max())
        typical = p95
        n = int(len(g))
        share_above = float((g["casts"] > typical).sum() / n) if n else 0.0
        reusable = bool((p99 > p95) or MODE.get(ability) == "placed")
        rows.append({
            "ability": ability,
            "agent": agent,
            "typical_charges": typical,
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "max": max_casts,
            "share_above": share_above,
            "reusable": reusable,
            "n_player_rounds": n,
        })

    out = pd.DataFrame(rows).sort_values(["ability", "agent"]).reset_index(drop=True)
    return out
