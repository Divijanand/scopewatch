"""Capability audit on a sample of series: what the feeds actually contain.

Answers, with counts:
  - which event types occur, and which are reversals ("!" actions)
  - whether each reversal matches an earlier event (same type minus "!", same actor and target)
  - which inventory events exist (purchase / pickup / drop) and their fields
  - how often positions are stale (same player, same xy across consecutive events)
  - plant / defuse coverage
Writes cache/audit/sample_audit.json (git-ignored) and prints a summary.

Usage: python -m scripts.audit_sample [--n 40]
"""
from __future__ import annotations

import argparse
import collections
import json
import random

import pandas as pd

from pipeline.config import CACHE_DIR, DATA_DIR
from pipeline.extract import stream


def audit_series(sid: str) -> dict:
    types = collections.Counter()
    rev = collections.Counter()
    rev_matched = collections.Counter()
    rev_examples = {}
    seen = collections.defaultdict(list)  # (type, actor, target) -> event ids
    last_pos = {}
    stale = fresh = 0
    inv_fields = {}
    plants = plants_with_pos = 0
    for env in stream(DATA_DIR / "val" / f"events_{sid}_grid.jsonl.zst"):
        for e in env["events"]:
            t = e["type"]
            types[t] += 1
            a, g = e.get("actor") or {}, e.get("target") or {}
            key = (t, a.get("id"), g.get("id"))
            if "-!" in t:
                rev[t] += 1
                orig = t.replace("-!", "-")
                okey = (orig, a.get("id"), g.get("id"))
                if seen.get(okey):
                    rev_matched[t] += 1
                    seen[okey].pop()
                if t not in rev_examples:
                    rev_examples[t] = dict(
                        actor=a.get("type") + ":" + str(a.get("id")), target=g.get("type") + ":" + str(g.get("id")),
                        had_prior=bool(seen.get(okey) is not None), occurredAt=env["occurredAt"])
            else:
                seen[key].append(e["id"])
            if t in ("player-purchased-item", "player-pickedUp-item", "player-dropped-item") and t not in inv_fields:
                inv_fields[t] = dict(target_state_keys=sorted((g.get("state") or {}).keys()),
                                     target_id=g.get("id"))
            if t == "player-completed-plantBomb":
                plants += 1
                pos = ((a.get("state") or {}).get("game") or {}).get("position")
                plants_with_pos += bool(pos)
            if a.get("type") == "player":
                pos = ((a.get("state") or {}).get("game") or {}).get("position")
                if pos:
                    k = a["id"]
                    xy = (pos["x"], pos["y"])
                    if last_pos.get(k) == xy:
                        stale += 1
                    else:
                        fresh += 1
                    last_pos[k] = xy
    return dict(series_id=sid, types=types, reversals=rev, reversals_matched=rev_matched,
                reversal_examples=rev_examples, inventory_fields=inv_fields,
                stale_positions=stale, fresh_positions=fresh, plants=plants, plants_with_pos=plants_with_pos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    args = ap.parse_args()
    s = pd.read_csv(DATA_DIR / "val" / "series.csv", dtype={"series_id": str})
    # stratify: a few series from every event so sampling covers 1 Hz and 5 Hz, VCT and GC
    rng = random.Random(7)
    by_event = s.groupby("event").series_id.apply(list).to_dict()
    pick = []
    while len(pick) < args.n:
        for ev, ids in by_event.items():
            if ids and len(pick) < args.n:
                pick.append(ids.pop(rng.randrange(len(ids))))
    from multiprocessing import Pool
    with Pool(4) as p:
        res = p.map(audit_series, pick)

    tot = collections.Counter(); rev = collections.Counter(); revm = collections.Counter()
    ex = {}; inv = {}
    stale = fresh = plants = plants_pos = 0
    for r in res:
        tot.update(r["types"]); rev.update(r["reversals"]); revm.update(r["reversals_matched"])
        ex.update(r["reversal_examples"]); inv.update(r["inventory_fields"])
        stale += r["stale_positions"]; fresh += r["fresh_positions"]
        plants += r["plants"]; plants_pos += r["plants_with_pos"]
    out = dict(series=pick, event_types=tot.most_common(), reversals=rev.most_common(),
               reversals_matched=dict(revm), reversal_examples=ex, inventory_fields=inv,
               stale_position_share=round(stale / max(1, stale + fresh), 4),
               plants=plants, plants_with_position=plants_pos)
    (CACHE_DIR / "audit").mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "audit" / "sample_audit.json").write_text(json.dumps(out, indent=1, default=str))
    print(f"series sampled: {len(pick)}")
    print("event types:", len(tot))
    for t, n in tot.most_common():
        print(f"  {n:>8}  {t}")
    print("reversals (matched to a prior event / total):")
    for t, n in rev.most_common():
        print(f"  {revm.get(t, 0):>5}/{n:<5} {t}  e.g. {ex[t]}")
    print("inventory event fields:", json.dumps(inv))
    print(f"stale positions: {out['stale_position_share']:.1%} of player-actor events repeat the previous xy")
    print(f"plants: {plants}, with actor position: {plants_pos}")


if __name__ == "__main__":
    main()
