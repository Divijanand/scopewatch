"""VOD links: one VOD per game, synced by the analyst at one or more rounds.

The feed has wall-clock times for every event, so one sync point is enough to place every round:

    vod_time(round R buy end) = sync.vod_s + (buy_end_ms[R] - buy_end_ms[sync round]) / 1000
    vod_time(event)           = vod_time(round buy end) + event.t_round

A broadcast VOD runs in real time (tech pauses and replays included), so one sync holds for the
whole map. An edited VOD (pauses cut) drifts; the analyst adds another sync at any round and each
round uses the nearest sync at or before it (or the first one after it).

Stored in a separate SQLite file (cache/v2/user.sqlite, git-ignored): these are the analyst's
notes, not GRID data, and never go into the analytical store.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlparse

from .config import CACHE_DIR

USER_DB = CACHE_DIR / "v2" / "user.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS vod_links (game_id TEXT PRIMARY KEY, url TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vod_syncs (game_id TEXT NOT NULL, round_no INTEGER NOT NULL, vod_s REAL NOT NULL,
                                      updated_at TEXT NOT NULL, PRIMARY KEY (game_id, round_no));
"""


def _db(path=None):
    p = path or USER_DB
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p)
    c.executescript(SCHEMA)
    return c


def valid_url(url: str) -> bool:
    u = urlparse(url)
    return u.scheme in ("http", "https") and bool(u.netloc)


def save(game_id: str, url: str | None = None, round_no: int | None = None, vod_s: float | None = None, path=None):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _db(path) as c:
        if url is not None:
            if not valid_url(url):
                raise ValueError("VOD link must be an http(s) URL")
            c.execute("INSERT INTO vod_links VALUES (?, ?, ?) ON CONFLICT(game_id) DO UPDATE "
                      "SET url = excluded.url, updated_at = excluded.updated_at", (game_id, url, now))
        if round_no is not None and vod_s is not None:
            if vod_s < 0:
                raise ValueError("VOD time can't be negative")
            c.execute("INSERT INTO vod_syncs VALUES (?, ?, ?, ?) ON CONFLICT(game_id, round_no) DO UPDATE "
                      "SET vod_s = excluded.vod_s, updated_at = excluded.updated_at", (game_id, round_no, vod_s, now))


def clear(game_id: str, path=None):
    with _db(path) as c:
        c.execute("DELETE FROM vod_links WHERE game_id = ?", (game_id,))
        c.execute("DELETE FROM vod_syncs WHERE game_id = ?", (game_id,))


def get(game_id: str, path=None):
    with _db(path) as c:
        row = c.execute("SELECT url FROM vod_links WHERE game_id = ?", (game_id,)).fetchone()
        syncs = c.execute("SELECT round_no, vod_s FROM vod_syncs WHERE game_id = ? ORDER BY round_no",
                          (game_id,)).fetchall()
    return (row[0] if row else None), syncs


def round_times(buy_end_ms: dict[int, int], syncs: list[tuple[int, float]]) -> dict[int, dict]:
    """VOD second of each round's buy-phase end, and which sync it came from."""
    syncs = [(r, s) for r, s in syncs if r in buy_end_ms and buy_end_ms[r] is not None]
    if not syncs:
        return {}
    out = {}
    for r, ms in buy_end_ms.items():
        if ms is None:
            continue
        before = [s for s in syncs if s[0] <= r]
        sr, ss = before[-1] if before else syncs[0]
        out[r] = dict(buy_end_s=round(ss + (ms - buy_end_ms[sr]) / 1000.0, 1), synced_at_round=sr)
    return out
