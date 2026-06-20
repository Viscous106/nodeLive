"""Pure watch-coverage core: union of played spans, clamping, and the
compliance rule that seeking to the end yields partial — never 100%."""

from app.utils.watch import apply_heartbeat


def test_contiguous_play_accumulates():
    r = apply_heartbeat([], 0.0, 30.0, duration=100.0)
    assert r["segments"] == [[0.0, 30.0]]
    assert abs(r["percent_complete"] - 0.30) < 1e-9


def test_reconnect_overlap_unioned_not_summed():
    r = apply_heartbeat([[0.0, 30.0]], 20.0, 50.0, duration=100.0)
    assert r["segments"] == [[0.0, 50.0]]
    assert abs(r["percent_complete"] - 0.50) < 1e-9


def test_seek_to_end_yields_partial_not_full():
    # Watched 0–15, then dragged the scrubber to the end and watched 99–100.
    r = apply_heartbeat([[0.0, 15.0]], 99.0, 100.0, duration=100.0)
    assert r["segments"] == [[0.0, 15.0], [99.0, 100.0]]
    # 16s of 100s, NOT 100%.
    assert abs(r["percent_complete"] - 0.16) < 1e-9


def test_played_to_clamped_to_duration():
    # A bogus played_to beyond the recording length can't exceed 100%.
    r = apply_heartbeat([], 0.0, 999.0, duration=100.0)
    assert r["segments"] == [[0.0, 100.0]]
    assert r["percent_complete"] == 1.0


def test_negative_from_clamped_to_zero():
    r = apply_heartbeat([], -5.0, 10.0, duration=100.0)
    assert r["segments"] == [[0.0, 10.0]]


def test_zero_duration_is_zero_percent():
    r = apply_heartbeat([], 0.0, 10.0, duration=0.0)
    assert r["percent_complete"] == 0.0
