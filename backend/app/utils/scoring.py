"""Pure scoring helpers for live polls and quizzes.

Kept free of DB/IO so the rules are unit-tested directly (quiz speed bonus,
poll percentages) — the live feature DoD requires this coverage.
"""

# Participation reward for answering a poll, regardless of choice.
POLL_POINTS = 5

# Quiz answer points: a correct answer earns between MIN and MAX scaled by how
# much of the question's time window was left when it was submitted.
QUIZ_MIN_POINTS = 2
QUIZ_MAX_POINTS = 10


def score_answer(
    *,
    is_correct: bool,
    time_remaining_secs: float,
    time_limit_secs: float,
    max_points: int = QUIZ_MAX_POINTS,
    min_points: int = QUIZ_MIN_POINTS,
) -> int:
    """Points for a quiz answer.

    Wrong, late (no time left), or a non-positive limit all score 0. A correct
    answer scales with the fraction of time remaining, clamped to
    [min_points, max_points] so an instant answer caps at max and a slow-but-
    in-time answer floors at min.
    """
    if not is_correct or time_limit_secs <= 0 or time_remaining_secs <= 0:
        return 0
    fraction = min(time_remaining_secs / time_limit_secs, 1.0)
    return max(min_points, min(max_points, round(max_points * fraction)))


def poll_percentages(counts: list[int]) -> list[dict]:
    """Per-option tally as `[{optionIndex, count, pct}]`.

    Percentages are whole numbers over the total responses; an empty poll
    yields 0% for every option (no division by zero).
    """
    total = sum(counts)
    return [
        {
            "optionIndex": i,
            "count": c,
            "pct": round(100 * c / total) if total else 0,
        }
        for i, c in enumerate(counts)
    ]
