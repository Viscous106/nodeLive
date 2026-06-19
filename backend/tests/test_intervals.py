"""Interval-union compliance primitive (ported from testing/lib/intervals.js).

Used by attendance reconcile AND watch-tracking: union real spans so reconnects
can't double-count and seeking to the end can't fake completion.
"""

from app.utils.intervals import coverage_fraction, covered_seconds, merge_intervals


def test_merge_overlapping():
    assert merge_intervals([[0, 10], [5, 15]]) == [(0, 15)]


def test_merge_disjoint_and_unsorted():
    assert merge_intervals([[10, 15], [0, 5]]) == [(0, 5), (10, 15)]


def test_merge_adjacent():
    assert merge_intervals([[0, 5], [5, 10]]) == [(0, 10)]


def test_merge_ignores_invalid_and_zero_length():
    assert merge_intervals([[5, 5], [3, 1], [0, 10], "x", [1]]) == [(0, 10)]


def test_merge_empty():
    assert merge_intervals([]) == []


def test_covered_seconds_is_union_not_sum():
    # raw sum is 10 + 10 = 20; union [0,15] = 15
    assert covered_seconds([[0, 10], [5, 15]]) == 15


def test_seek_to_end_does_not_yield_full_coverage():
    # THE compliance case: watching [0,5] + [90,100] of a 100s recording is 15%,
    # not the 100% a naive currentTime/duration would report.
    assert coverage_fraction([[0, 5], [90, 100]], 100) == 0.15


def test_coverage_clamps_and_guards_bad_totals():
    assert coverage_fraction([[0, 200]], 100) == 1
    assert coverage_fraction([[0, 10]], 0) == 0
    assert coverage_fraction([], 100) == 0
