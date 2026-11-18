"""Supplement quality states: each gets an explicit, documented geometry decision (S5)."""
import pytest

from engine.ingest.reducer import SeriesReducer
from tests.synth import cast


def geo(**kw):
    return SeriesReducer._cast_geometry(cast("S", "G", 1, "p", **kw))


def test_ok_uses_interpolated_position():
    src, how, dt, low = geo(quality="ok", offsets=(-80, 120))
    assert how == "interpolated" and dt == 80 and not low


@pytest.mark.parametrize("q", ["missing_after", "missing_before"])
def test_one_sided_uses_supplied_estimate_and_says_so(q):
    offs = (-60, None) if q == "missing_after" else (None, 60)
    src, how, dt, _ = geo(quality=q, offsets=offs)
    assert how == q and dt == 60 and src is not None


def test_gap_exceeded_uses_closer_real_frame():
    src, how, dt, _ = geo(quality="gap_exceeded", offsets=(-40, 1500))
    assert how == "frame_before" and dt == 40


def test_missing_both_has_no_geometry_never_zero():
    src, how, dt, _ = geo(quality="missing_both", offsets=(None, None))
    assert src is None and how is None and dt is None


def test_low_rate_series_detected_from_frame_spacing():
    *_, low = geo(quality="ok", offsets=(-500, 500))   # ~1 Hz sampling
    assert low
