"""Fill in kills that GRID records without a weapon.

Some kills arrive with no weapon (Chamber's Tour de Force, some ability kills), but GRID sends
the matching damage event, with the weapon, from the same attacker on the same victim within a
few milliseconds. A weaponless kill takes the weapon of that damage event; `weapon_inferred`
marks it. Kills with no matching damage event stay unknown (never guessed).
"""
from __future__ import annotations

MATCH_MS = 50

SNIPERS = ("operator", "outlaw", "tour-de-force")   # Chamber's ult counts as an Operator for kill metrics

GUNS = frozenset({
    "classic", "shorty", "frenzy", "ghost", "sheriff", "bandit", "stinger", "spectre", "bucky",
    "judge", "bulldog", "guardian", "phantom", "vandal", "marshal", "outlaw", "operator", "ares",
    "odin", "blade-storm", "tour-de-force", "overdrive",
})


def backfill(con) -> dict:
    cols = {r[0] for r in con.execute("DESCRIBE engagements").fetchall()}
    if "weapon_inferred" not in cols:
        con.execute("ALTER TABLE engagements ADD COLUMN weapon_inferred BOOLEAN DEFAULT FALSE")
    before = con.execute("SELECT count(*) FROM engagements WHERE kind = 'kill' AND weapon IS NULL").fetchone()[0]
    con.execute(f"""
        WITH m AS (
          SELECT k.event_id,
                 arg_min(d.weapon, abs(d.ts_ms - k.ts_ms)) AS weapon
          FROM engagements k
          JOIN engagements d ON d.round_key = k.round_key AND d.att_id = k.att_id AND d.vic_id = k.vic_id
           AND d.kind = 'damage' AND d.weapon IS NOT NULL AND d.weapon <> 'unknown'
           AND abs(d.ts_ms - k.ts_ms) <= {MATCH_MS}
          WHERE k.kind = 'kill' AND k.weapon IS NULL
          GROUP BY k.event_id)
        UPDATE engagements SET weapon = m.weapon, weapon_inferred = TRUE
        FROM m WHERE engagements.event_id = m.event_id AND engagements.kind = 'kill'""")
    after = con.execute("SELECT count(*) FROM engagements WHERE kind = 'kill' AND weapon IS NULL").fetchone()[0]
    top = con.execute("""SELECT weapon, count(*) FROM engagements WHERE weapon_inferred
                         GROUP BY 1 ORDER BY 2 DESC LIMIT 8""").fetchall()
    return dict(null_before=before, null_after=after, filled=before - after, by_weapon=top)
