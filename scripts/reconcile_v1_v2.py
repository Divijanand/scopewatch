"""Compare v1 (no in-game reversal handling) with v2 on the same games, and summarise ingest health.

Prints corpus totals from the v2 manifest (events, reversals, LIFO vs not, voided rows, casts excluded)
and the v1 -> v2 difference in rounds, kills and Operator kills on games both versions kept.

Usage: python -m scripts.reconcile_v1_v2
"""
import json

import duckdb
import pandas as pd

from engine.config import CACHE_DIR, MANIFEST_PATH, RAW_DIR

V1 = (CACHE_DIR / "raw").as_posix()
V2 = RAW_DIR.as_posix()


def main():
    man = pd.read_parquet(MANIFEST_PATH)
    tot = {}
    for cj in man.counts_json:
        for k, v in json.loads(cj).items():
            if isinstance(v, (int, float)):
                tot[k] = tot.get(k, 0) + v
    print(f"series: {len(man)}  ok: {(man.status == 'ok').sum()}  failed: {(man.status != 'ok').sum()}")
    for k in ["events_in", "reversals_in", "reversals_lifo", "reversals_non_lifo", "reversals_unmatched",
              "casts_in", "casts_excluded.reversed_in_grid", "casts_no_geometry", "casts_round_unknown",
              "engagement_weapon_unknown", "quarantined.feed", "quarantined.supplement"]:
        print(f"  {k:34s} {int(tot.get(k, 0)):>12,}")
    for k in sorted(x for x in tot if x.startswith("rows_voided.")):
        print(f"  {k:34s} {int(tot[k]):>12,}")

    c = duckdb.connect()
    q = lambda base, sql: c.execute(sql.replace("{B}", base)).fetchall()  # noqa: E731
    for label, sql in [
        ("rounds", "SELECT count(*) FROM read_parquet('{B}/rounds/*.parquet', union_by_name=true)"),
        ("kills", "SELECT count(*) FROM read_parquet('{B}/engagements/*.parquet', union_by_name=true) WHERE kind='kill'"),
        ("operator/outlaw kills", "SELECT count(*) FROM read_parquet('{B}/engagements/*.parquet', union_by_name=true) "
                                  "WHERE kind='kill' AND weapon IN ('operator','outlaw')"),
    ]:
        v1, v2 = q(V1, sql)[0][0], q(V2, sql)[0][0]
        print(f"{label:24s} v1 {v1:>9,}  v2 {v2:>9,}  diff {v2 - v1:>+7,} ({(v2 - v1) / v1:+.3%})")


if __name__ == "__main__":
    main()
