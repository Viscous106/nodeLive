"""Interval-union helpers — the core compliance primitive.

Ported from `testing/lib/intervals.js`. Used in two places with identical
semantics:
  - Attendance: union a participant's join↔leave spans so reconnects don't
    double-count "present" time.
  - Watch tracking: union the spans a viewer ACTUALLY played, so seeking to the
    end can never inflate coverage.

An interval is ``(start, end)`` with ``end > start`` (seconds or epoch ms — the
math is unit-agnostic). Zero-length and inverted intervals are ignored.
"""

import math
from collections.abc import Iterable, Sequence

Interval = tuple[float, float]


def _is_valid(iv: object) -> bool:
    return (
        isinstance(iv, Sequence)
        and not isinstance(iv, str | bytes)
        and len(iv) == 2
        and isinstance(iv[0], int | float)
        and isinstance(iv[1], int | float)
        and math.isfinite(iv[0])
        and math.isfinite(iv[1])
        and iv[1] > iv[0]
    )


def merge_intervals(intervals: Iterable[object] | None) -> list[Interval]:
    """Merge overlapping/adjacent intervals into a minimal, sorted, disjoint set."""
    cleaned = sorted(
        (float(iv[0]), float(iv[1])) for iv in (intervals or []) if _is_valid(iv)
    )
    if not cleaned:
        return []

    out: list[list[float]] = [list(cleaned[0])]
    for start, end in cleaned[1:]:
        last = out[-1]
        if start <= last[1]:
            last[1] = max(last[1], end)  # overlap/adjacency → extend
        else:
            out.append([start, end])
    return [(s, e) for s, e in out]


def covered_seconds(intervals: Iterable[object] | None) -> float:
    """Total covered length after union."""
    return sum(e - s for s, e in merge_intervals(intervals))


def coverage_fraction(intervals: Iterable[object] | None, total: float) -> float:
    """Fraction of ``total`` covered, clamped to [0, 1]; 0 for non-positive total."""
    if not isinstance(total, int | float) or not math.isfinite(total) or total <= 0:
        return 0.0
    return max(0.0, min(1.0, covered_seconds(intervals) / total))
