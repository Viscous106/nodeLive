"""Watch-coverage core — the client-reported half of the compliance model.

Credit comes ONLY from the union of actually-played spans (via `intervals.py`),
so dragging the scrubber to the end never earns credit for skipped regions.
Pure and IO-free; the API layer persists the result.
"""

from app.utils.intervals import coverage_fraction, merge_intervals


def apply_heartbeat(
    prev_segments: list | None,
    played_from: float,
    played_to: float,
    duration: float,
) -> dict:
    """Fold a newly-played [from, to] span into prior segments; recompute %.

    `played_from`/`played_to` are clamped to [0, duration] (when duration > 0)
    so a bogus client span can't push coverage past 100%.
    """
    lo, hi = float(played_from), float(played_to)
    if duration and duration > 0:
        lo = max(0.0, min(lo, duration))
        hi = max(0.0, min(hi, duration))
    merged = merge_intervals([*(prev_segments or []), [lo, hi]])
    segments = [[s, e] for s, e in merged]
    return {
        "segments": segments,
        "percent_complete": coverage_fraction(segments, duration),
    }
