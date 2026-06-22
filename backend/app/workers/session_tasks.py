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
from app.models.attendance import Meeting
from app.models.course import ClassSession, SessionStatus
from app.workers import attendance_tasks
from app.workers.celery_app import celery_app

# Sessions are considered stale this long after their scheduled start.
_STALE_AFTER = timedelta(hours=2)


@celery_app.task(name="sessions.janitor")
def session_janitor() -> int:
    return asyncio.run(_run_janitor())


async def _run_janitor(session_factory=None, reconcile=None) -> int:
    # session_factory is an injection seam for tests (defaults to the app's
    # AsyncSessionLocal, which the janitor opens itself — it has no request scope).
    # reconcile is the attendance scheduler (injectable for tests).
    session_factory = session_factory or AsyncSessionLocal
    reconcile = reconcile or attendance_tasks.schedule_reconcile
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
        # Collect the Zoom meeting UUIDs to reconcile before the session expires.
        uuids: list[str] = []
        for cs in stale:
            cs.status = SessionStatus.ENDED
            cs.ended_at = datetime.now(UTC)
            if cs.zoom_meeting_id:
                uuids.extend(
                    await db.scalars(
                        select(Meeting.zoom_uuid).where(
                            Meeting.zoom_meeting_id == cs.zoom_meeting_id
                        )
                    )
                )
        if stale:
            await db.commit()
    # Schedule reconcile after the commit so an auto-ended session still gets its
    # authoritative attendance (the webhook that would have triggered it was lost).
    for u in uuids:
        reconcile(u)
    return len(stale)
