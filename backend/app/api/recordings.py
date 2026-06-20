"""Session-scoped recording playback + compliance watch-tracking.

Resolution: ClassSession.zoom_meeting_id → the Meeting occurrence with a stored
recording and the most recent ended_at. Watch credit is the union of played
spans; duration is server-authoritative (Meeting.recording_duration_secs),
falling back to the client only when unknown.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.live import _member_session  # enrolled / host / admin guard
from app.auth.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.attendance import Meeting, WatchProgress
from app.models.course import ClassSession
from app.models.user import User
from app.schemas.recording import (
    HeartbeatIn,
    ProgressOut,
    RecordingUrlOut,
    WatchStatusOut,
)
from app.utils.recording_storage import is_configured, presign_get
from app.utils.watch import apply_heartbeat

router = APIRouter(tags=["recordings"])


async def _resolve_recording(db: AsyncSession, cs: ClassSession) -> Meeting | None:
    """The stored recording occurrence for this session (latest ended_at)."""
    if not cs.zoom_meeting_id:
        return None
    return await db.scalar(
        select(Meeting)
        .where(
            Meeting.zoom_meeting_id == cs.zoom_meeting_id,
            Meeting.recording_status == "stored",
            Meeting.recording_s3_key.is_not(None),
        )
        .order_by(Meeting.ended_at.desc().nullslast())
        .limit(1)
    )


@router.get("/sessions/{session_id}/recording/url", response_model=RecordingUrlOut)
async def get_recording_url(
    cs: ClassSession = Depends(_member_session),
    db: AsyncSession = Depends(get_db),
):
    meeting = await _resolve_recording(db, cs)
    if meeting is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No recording available")
    if not is_configured():
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, "Recording playback not configured"
        )
    url = presign_get(meeting.recording_s3_key, settings.RECORDING_URL_TTL_SECS)
    return RecordingUrlOut(url=url, expires_in_secs=settings.RECORDING_URL_TTL_SECS)


async def _progress_row(
    db: AsyncSession, zoom_uuid: str, user_id: str
) -> WatchProgress | None:
    return await db.scalar(
        select(WatchProgress).where(
            WatchProgress.zoom_uuid == zoom_uuid,
            WatchProgress.user_id == user_id,
        )
    )


@router.get("/sessions/{session_id}/recording/progress", response_model=ProgressOut)
async def get_progress(
    cs: ClassSession = Depends(_member_session),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meeting = await _resolve_recording(db, cs)
    if meeting is None:
        return ProgressOut(last_position_secs=0, percent_complete=0, segments=[])
    row = await _progress_row(db, meeting.zoom_uuid, user.id)
    if row is None:
        return ProgressOut(last_position_secs=0, percent_complete=0, segments=[])
    return ProgressOut(
        last_position_secs=row.last_position_secs,
        percent_complete=row.percent_complete,
        segments=row.watched_segments or [],
    )


@router.post("/sessions/{session_id}/recording/heartbeat", response_model=ProgressOut)
async def heartbeat(
    body: HeartbeatIn,
    cs: ClassSession = Depends(_member_session),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meeting = await _resolve_recording(db, cs)
    if meeting is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No recording available")

    # Server-authoritative duration wins; client value is a fallback only.
    duration = (
        float(meeting.recording_duration_secs)
        if meeting.recording_duration_secs
        else body.duration
    )
    row = await _progress_row(db, meeting.zoom_uuid, user.id)
    prev = row.watched_segments if row else []
    result = apply_heartbeat(prev, body.played_from, body.played_to, duration)

    clamped_to = (
        min(max(body.played_to, 0.0), duration) if duration > 0 else body.played_to
    )
    if row is None:
        row = WatchProgress(zoom_uuid=meeting.zoom_uuid, user_id=user.id)
        db.add(row)
    row.watched_segments = result["segments"]
    row.percent_complete = result["percent_complete"]
    row.duration_secs = duration
    row.last_position_secs = clamped_to
    row.max_position_secs = max(row.max_position_secs or 0.0, clamped_to)
    row.updated_at = datetime.now(UTC)
    await db.commit()

    return ProgressOut(
        last_position_secs=row.last_position_secs,
        percent_complete=row.percent_complete,
        segments=row.watched_segments,
    )


@router.get(
    "/sessions/{session_id}/recording/watch-status", response_model=WatchStatusOut
)
async def watch_status(
    cs: ClassSession = Depends(_member_session),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meeting = await _resolve_recording(db, cs)
    if meeting is None:
        return WatchStatusOut(
            available=False,
            percent_complete=0,
            last_position_secs=0,
            duration_secs=None,
        )
    row = await _progress_row(db, meeting.zoom_uuid, user.id)
    return WatchStatusOut(
        available=True,
        percent_complete=row.percent_complete if row else 0.0,
        last_position_secs=row.last_position_secs if row else 0.0,
        duration_secs=(
            float(meeting.recording_duration_secs)
            if meeting.recording_duration_secs
            else None
        ),
    )
