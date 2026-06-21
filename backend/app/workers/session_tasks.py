"""Session lifecycle janitor — Celery beat task.

Safety net for webhook delivery failures: finds ClassSessions stuck in LIVE
status more than 2 hours past their scheduled start time and marks them ENDED.
Without this, a host who closes their tab without the `meeting.ended` webhook
firing would leave the session LIVE forever (and out of the Attendance tab).
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.course import ClassSession, SessionStatus
from app.workers.celery_app import celery_app

# Sessions are considered stale this long after their scheduled start.
_STALE_AFTER = timedelta(hours=2)


@celery_app.task(name="sessions.janitor")
def session_janitor() -> int:
    return asyncio.run(_run_janitor())


async def _run_janitor(session_factory=None) -> int:
    # session_factory is an injection seam for tests (defaults to the app's
    # AsyncSessionLocal, which the janitor opens itself — it has no request scope).
    session_factory = session_factory or AsyncSessionLocal
    cutoff = datetime.now(UTC) - _STALE_AFTER
    async with session_factory() as db:
        stale = list(
            await db.scalars(
                select(ClassSession).where(
                    ClassSession.status == SessionStatus.LIVE,
                    ClassSession.scheduled_at < cutoff,
                )
            )
        )
        for cs in stale:
            cs.status = SessionStatus.ENDED
            cs.ended_at = datetime.now(UTC)
        if stale:
            await db.commit()
    return len(stale)
