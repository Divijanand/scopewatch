"""Step 5b: the league table of dry duels by agent pair.

    python -m scripts.agent_duels        (needs cache/v2/models/fights.parquet: python -m engine.model.fights)

League-level only: no team names or ids go to docs/ (derived from licensed data).
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from engine.config import ROOT
from engine.metrics.core import bootstrap_mean
from engine.metrics.duels import CELL, FIGHTS_PARQUET, dry

MIN_PAIR = 300


def pair_rows(fights: pd.DataFrame) -> pd.DataFrame:
    """One row per dry fight from the view of the alphabetically first agent of the pair:
    won (1 if that agent's player won) and expected (the league's rate for the same cell, from its view)."""
    df = dry(fights).dropna(subset=["opener_agent", "other_agent"])
    df = df[(df["opener_agent"] != "") & (df["other_agent"] != "") & (df["opener_agent"] != df["other_agent"])]
    df = df.assign(planted=df["planted"].astype(bool))
    rate = df.groupby(CELL, dropna=False)["label"].transform("mean")
    first_is_opener = (df["opener_agent"] < df["other_agent"]).to_numpy()
    return pd.DataFrame({
        "agent_a": np.where(first_is_opener, df["opener_agent"], df["other_agent"]),
        "agent_b": np.where(first_is_opener, df["other_agent"], df["opener_agent"]),
        "won": np.where(first_is_opener, df["label"], 1 - df["label"]),
        "expected": np.where(first_is_opener, rate, 1 - rate),
        "series_id": df["series_id"].astype(str).to_numpy(),
    })


def table(rows: pd.DataFrame, min_pair: int = MIN_PAIR) -> pd.DataFrame:
    out = []
    for (a, b), g in rows.groupby(["agent_a", "agent_b"]):
        if len(g) < min_pair:
            continue
        diff = (g["won"] - g["expected"]).astype(float)
        lo, hi = bootstrap_mean(diff.tolist(), g["series_id"].tolist(), n=1000, seed=42)
        out.append(dict(agent_a=a, agent_b=b, n=len(g), won=g["won"].mean(), expected=g["expected"].mean(),
                        diff=diff.mean(), lo=lo, hi=hi))
    t = pd.DataFrame(out)
    if t.empty:
        return t
    # show each pair from the side that does better, then sort by the size of the gap
    flip = t["diff"] < 0
    t.loc[flip, ["agent_a", "agent_b"]] = t.loc[flip, ["agent_b", "agent_a"]].to_numpy()
    t.loc[flip, "won"] = 1 - t.loc[flip, "won"]
    t.loc[flip, "expected"] = 1 - t.loc[flip, "expected"]
    t.loc[flip, ["lo", "hi"]] = -t.loc[flip, ["hi", "lo"]].to_numpy()
    t.loc[flip, "diff"] = -t.loc[flip, "diff"]
    t["beyond_noise"] = (t["lo"] > 0) | (t["hi"] < 0)
    return t.sort_values(["diff", "n"], ascending=[False, False]).reset_index(drop=True)


def main():
    fights = pd.read_parquet(FIGHTS_PARQUET)
    rows = pair_rows(fights)
    t = table(rows)
    beyond = int(t["beyond_noise"].sum()) if len(t) else 0
    lines = [
        "# Dry duels by agent pair (league)",
        "",
        f"Run {datetime.now().isoformat(timespec='seconds')} on all series. {len(rows):,} dry fights between two "
        f"different agents; {len(t)} pairs with at least {MIN_PAIR} fights; {beyond} differ from expected beyond noise.",
        "",
        "Dry = no flash, stun, smoke, recon or ult cast near the fight by either team, and no ability damage to either "
        "fighter, in the 4 s before. **Expected** is the league's dry-fight opener win rate for the same map, opener side, "
        "alive counts and plant (flipped when the other agent opened), so who shot first is accounted for. "
        "**Points** = (won − expected) × 100 for the first agent. Ranges are 90% series-bootstrap t intervals (D-020). "
        "Association, not cause: agent choice comes with role, position and player.",
        "",
        f"- **Weapons aren't separated.** Chamber's Headhunter and Tour de Force, and the Operator (often on Chamber), "
        "are part of what an agent row measures.",
        f"- **Chance alone.** With {len(t)} pairs and 90% ranges, about {round(len(t) * 0.1)} pairs would show a range "
        f"that excludes 0 even if no agent pair differed; {beyond} do. Read single pairs as hints, and patterns "
        "across many pairs (one agent winning against most others) as the stronger signal.",
        "",
        "| Agent | Against | Fights | Won | Expected | Points | 90% range | Beyond noise |",
        "|---|---|---:|---:|---:|---:|---:|:---:|",
    ]
    for r in t.itertuples(index=False):
        lines.append(f"| {r.agent_a} | {r.agent_b} | {r.n:,} | {r.won:.1%} | {r.expected:.1%} | {r.diff * 100:+.1f} "
                     f"| [{r.lo * 100:+.1f}, {r.hi * 100:+.1f}] | {'yes' if r.beyond_noise else ''} |")
    out = ROOT / "docs" / "AGENT_DUELS.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out}: {len(t)} pairs, {beyond} beyond noise")


if __name__ == "__main__":
    main()
