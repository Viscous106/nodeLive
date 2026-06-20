"""Recording → R2 ingest (Celery), mirroring `attendance_tasks.py`.

On `recording.completed`, download the MP4 (prefer the webhook `download_token`;
fall back to S2S OAuth) and stream it to R2, then mark the meeting `stored`.
The pure `run_ingest` sits behind injection seams (`get_token`,
`http_get_stream`, `upload`, `mark`) so the wiring is tested offline; the live
httpx/boto3/DB path is ported verbatim and exercised only with real creds.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.attendance import Meeting
from app.utils.attendance import parse_zoom_time
from app.utils.recording_storage import pick_mp4, upload_stream
from app.utils.zoom_auth import get_zoom_access_token
from app.workers.celery_app import celery_app


def _duration_secs(file: dict) -> int | None:
    start = parse_zoom_time(file.get("recording_start"))
    end = parse_zoom_time(file.get("recording_end"))
    if start is not None and end is not None and end > start:
        return int(end - start)
    return None


async def _default_http_get_stream(url: str) -> AsyncIterator[bytes]:
    async with (
        httpx.AsyncClient(timeout=None, follow_redirects=True) as client,
        client.stream("GET", url) as resp,
    ):
        resp.raise_for_status()
        async for chunk in resp.aiter_bytes():
            yield chunk


async def _default_upload(key: str, body: AsyncIterator[bytes]) -> str:
    # Bridge the async byte stream to the sync boto3 uploader off the event loop.
    chunks = [c async for c in body]
    await asyncio.to_thread(upload_stream, key, iter(chunks))
    return key


async def _default_mark(
    uuid: str, key: str | None, status: str, duration: int | None
) -> None:
    async with AsyncSessionLocal() as db:
        meeting = await db.scalar(select(Meeting).where(Meeting.zoom_uuid == uuid))
        if meeting is None:
            meeting = Meeting(zoom_uuid=uuid)
            db.add(meeting)
        meeting.recording_s3_key = key
        meeting.recording_status = status
        if duration is not None:
            meeting.recording_duration_secs = duration
        await db.commit()


async def run_ingest(
    uuid: str,
    download_token: str | None,
    recording_files: list[dict] | None,
    *,
    get_token: Callable[[], Awaitable[str]] | None = None,
    http_get_stream: Callable[[str], AsyncIterator[bytes]] | None = None,
    upload: Callable[[str, AsyncIterator[bytes]], Awaitable[str]] | None = None,
    mark: Callable[[str, str | None, str, int | None], Awaitable[None]] | None = None,
) -> str:
    if not uuid:
        raise ValueError("ingest: missing zoom_uuid")
    get_token = get_token or get_zoom_access_token
    http_get_stream = http_get_stream or _default_http_get_stream
    upload = upload or _default_upload
    mark = mark or _default_mark

    file = pick_mp4(recording_files)
    if file is None:
        await mark(uuid, None, "failed", None)
        raise ValueError("ingest: no MP4 in recording_files")

    token = download_token or await get_token()
    download_url = file["download_url"]
    sep = "&" if "?" in download_url else "?"
    url = f"{download_url}{sep}access_token={token}"

    key = f"recordings/{uuid}.mp4"
    await upload(key, http_get_stream(url))
    await mark(uuid, key, "stored", _duration_secs(file))
    return key


@celery_app.task(name="recording.ingest")
def ingest_recording(
    uuid: str, download_token: str | None, recording_files: list[dict]
) -> str:
    return asyncio.run(run_ingest(uuid, download_token, recording_files))


def schedule_ingest(
    uuid: str, download_token: str | None, recording_files: list[dict]
) -> None:
    """Enqueue the ingest job (best-effort; the webhook already acked)."""
    ingest_recording.apply_async(args=[uuid, download_token, recording_files])
