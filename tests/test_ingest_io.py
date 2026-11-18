import collections

import zstandard

from engine.ingest.run import stream_jsonl_zst


def test_malformed_lines_are_quarantined_not_fatal(tmp_path):
    p = tmp_path / "f.jsonl.zst"
    p.write_bytes(zstandard.ZstdCompressor().compress(b'{"a":1}\n{broken\n\n{"a":2}\n'))
    counts = collections.Counter()
    rows = list(stream_jsonl_zst(p, counts, "feed"))
    assert rows == [{"a": 1}, {"a": 2}]
    assert counts["quarantined.feed"] == 1
    assert counts["_quarantine_lines"] == ["feed:2"]
