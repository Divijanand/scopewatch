from __future__ import annotations

import duckdb

from engine.config import DB_PATH, ROOT
from engine.model.charges import estimate_charges


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = estimate_charges(con).sort_values(["ability", "agent"]) 
    con.close()

    lines = [
        "# Ability charge estimates (step 4b)",
        "",
        "Aggregated from casts in phases `buy`, `pre_plant`, `post_plant` after merging same-player same-ability events within <1.0s.",
        "",
        "| ability | agent | typical_charges | p50 | p95 | p99 | max | share_above | reusable | n_player_rounds |",
        "|---|---|---:|---:|---:|---:|---:|---:|:---:|---:|",
    ]
    for r in df.itertuples(index=False):
        lines.append(
            "| "
            + f"{r.ability} | {r.agent} | {int(r.typical_charges)} | {int(r.p50)} | {int(r.p95)} | "
            + f"{int(r.p99)} | {int(r.max)} | {float(r.share_above):.4f} | "
            + f"{'yes' if bool(r.reusable) else 'no'} | {int(r.n_player_rounds)} |"
        )

    (ROOT / "docs" / "ABILITY_CHARGES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
