"""Pure scoring rules — quiz speed bonus and poll percentages."""

from app.utils.scoring import poll_percentages, score_answer


def test_instant_correct_answer_caps_at_max():
    assert (
        score_answer(is_correct=True, time_remaining_secs=30, time_limit_secs=30) == 10
    )


def test_slow_correct_answer_floors_at_min():
    # 1s left of 30 → 0.33 pts raw, clamped up to the 2-point minimum.
    assert score_answer(is_correct=True, time_remaining_secs=1, time_limit_secs=30) == 2


def test_half_time_scales_between():
    assert (
        score_answer(is_correct=True, time_remaining_secs=15, time_limit_secs=30) == 5
    )


def test_wrong_answer_scores_zero():
    assert (
        score_answer(is_correct=False, time_remaining_secs=30, time_limit_secs=30) == 0
    )


def test_late_answer_scores_zero_not_minimum():
    # Answered after the window closed — no credit, not the 2-point floor.
    assert score_answer(is_correct=True, time_remaining_secs=0, time_limit_secs=30) == 0
    assert (
        score_answer(is_correct=True, time_remaining_secs=-5, time_limit_secs=30) == 0
    )


def test_non_positive_limit_is_safe():
    assert score_answer(is_correct=True, time_remaining_secs=5, time_limit_secs=0) == 0


def test_poll_percentages_round_to_whole():
    # 1 vs 2 of 3 → 33% / 67%.
    results = poll_percentages([1, 2])
    assert results == [
        {"optionIndex": 0, "count": 1, "pct": 33},
        {"optionIndex": 1, "count": 2, "pct": 67},
    ]


def test_poll_percentages_empty_is_zero_not_divide_by_zero():
    assert poll_percentages([0, 0]) == [
        {"optionIndex": 0, "count": 0, "pct": 0},
        {"optionIndex": 1, "count": 0, "pct": 0},
    ]
