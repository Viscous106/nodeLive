"""Server-side quiz timer.

When the instructor launches a quiz, the route calls `schedule_quiz_questions`,
which enqueues one delayed `emit_event` task per question plus a final
`quiz:ended` — so questions rotate on a server clock the client can't fake.

The worker is a separate (sync) process and cannot use the async server's
socket manager, so it emits through a write-only `RedisManager`. Each question's
payload is baked in at schedule time; the task does no DB work, which keeps it
idempotent and cheap to retry.
"""

from functools import lru_cache

import socketio

from app.core.config import settings
from app.realtime.rooms import session_room
from app.workers.celery_app import celery_app


@lru_cache(maxsize=1)
def _manager() -> socketio.RedisManager:
    return socketio.RedisManager(settings.REDIS_URL, write_only=True)


@celery_app.task(name="quiz.emit_event")
def emit_event(session_id: str, event: str, payload: dict) -> None:
    """Emit a single live event to a session room (used by the quiz timer)."""
    _manager().emit(event, payload, room=session_room(session_id))


def schedule_quiz_questions(
    *,
    session_id: str,
    quiz_id: str,
    questions: list[dict],
    time_limit_secs: int,
) -> None:
    """Enqueue the timed rotation: each question, then `quiz:ended`.

    `questions` is an ordered list of `{questionId, text, options}` (no correct
    answer — that never goes to clients). Question N fires at N*time_limit; the
    ended event fires after the last window closes.
    """
    for index, question in enumerate(questions):
        emit_event.apply_async(
            args=[
                session_id,
                "quiz:next-question",
                {
                    "quizId": quiz_id,
                    "index": index,
                    "timeLeft": time_limit_secs,
                    **question,
                },
            ],
            countdown=index * time_limit_secs,
        )
    emit_event.apply_async(
        args=[session_id, "quiz:ended", {"quizId": quiz_id}],
        countdown=len(questions) * time_limit_secs,
    )
