# M7 — Recording Ingest + Watch-Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A class recording lands in Cloudflare R2 via a seam-tested Zoom ingest job, students watch it through a compliance-grade player, and watch credit is computed from the union of actually-played spans (seek-to-end ≠ 100%), exposed as a read-model for Dev A's dashboard.

**Architecture:** Recording columns live on the existing `Meeting` table (keyed by `zoom_uuid`). Ingest is a Celery task mirroring `attendance_tasks.py` — a pure core behind injection seams (`get_token`, `http_get_stream`, `upload`, `mark`) so it is fully unit-tested offline; the live Zoom-download path is ported verbatim and raises until creds are set. Watch-tracking is session-scoped REST (`/api/sessions/{id}/recording/*`) reusing `intervals.py` for the union and real `get_current_user` identity. Playback uses boto3 S3 presigned GET URLs (portable R2/S3), returning 501 when unconfigured.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 async · Alembic · Celery · boto3 (R2/S3) · httpx · React 19 + TS · TanStack Query.

**Spec:** `docs/superpowers/specs/2026-06-20-m7-recording-ingest-watch-tracking-design.md`

> **Git note:** This project's owner runs all git commands themselves and commits directly to `main`. The "Commit" steps below are the exact messages to use — surface them to the owner; the implementing agent does NOT run git.

---

## File Structure

**Backend (create unless noted):**
- `app/models/attendance.py` *(modify)* — add `recording_*` columns to `Meeting`; add `WatchProgress` model.
- `alembic/versions/<rev>_recording_watch_tracking.py` — migration.
- `app/utils/recording_storage.py` — R2 boto3 helper (`pick_mp4`, client, `upload_stream`, `presign_get`, `is_configured`).
- `app/workers/recording_tasks.py` — `run_ingest` (pure + seams) + `ingest_recording` Celery task + `schedule_ingest`.
- `app/api/webhooks.py` *(modify)* — `recording.completed` branch.
- `app/schemas/recording.py` — Pydantic request/response models.
- `app/api/recordings.py` — session-scoped watch-tracking routes.
- `app/core/config.py` *(modify)* — `R2_*` + `RECORDING_URL_TTL_SECS`.
- `app/main.py` *(modify)* — include `recordings.router`.
- `backend/.env.example` *(modify)* — document `R2_*`.
- `tests/test_recording_heartbeat.py`, `tests/test_recording_ingest.py`, `tests/test_recording_api.py`.

**Frontend (create unless noted):**
- `src/hooks/useRecording.ts` — url/progress/heartbeat/watch-status query+mutation hooks.
- `src/pages/RecordingPlayerPage.tsx` — the player (faithful port of `testing/src/RecordingPlayer.tsx`).
- `src/router.tsx` *(modify)* — add `/session/:sessionId/recording`.

---

## Task 1: Config + env for R2

**Files:**
- Modify: `app/core/config.py` (after `ATTENDANCE_RECONCILE_DELAY_SECS`, line ~68)
- Modify: `backend/.env.example`

- [ ] **Step 1: Add settings**

In `app/core/config.py`, after the `ATTENDANCE_RECONCILE_DELAY_SECS` line and before `# --- AI ---`:

```python
    # --- Recording storage (Cloudflare R2 / S3-compatible) ---
    # All empty by default → ingest + presign raise/501 (graceful degrade).
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = ""
    # e.g. https://<account_id>.r2.cloudflarestorage.com
    R2_ENDPOINT_URL: str = ""
    # Presigned playback URL lifetime.
    RECORDING_URL_TTL_SECS: int = 300
```

- [ ] **Step 2: Document env**

Append to `backend/.env.example`:

```bash
# --- Recording storage (Cloudflare R2 / S3-compatible) ---
# Leave blank to disable recording ingest + playback (endpoints 501 gracefully).
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=
R2_ENDPOINT_URL=
RECORDING_URL_TTL_SECS=300
```

- [ ] **Step 3: Verify it loads**

Run: `cd backend && python -c "from app.core.config import settings; print(settings.RECORDING_URL_TTL_SECS, repr(settings.R2_BUCKET))"`
Expected: `300 ''`

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/config.py backend/.env.example
git commit -m "feat(recordings): R2 storage settings + env"
```

---

## Task 2: Data model — recording columns + WatchProgress

**Files:**
- Modify: `app/models/attendance.py`
- Test: `tests/test_recording_api.py` (model smoke, expanded later)

- [ ] **Step 1: Add columns to `Meeting`**

In `app/models/attendance.py`, inside `class Meeting`, after the `ended_at` column:

```python
    recording_s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    recording_status: Mapped[str] = mapped_column(
        String(16), default="none", nullable=False
    )  # none | pending | stored | failed
    recording_duration_secs: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
```

- [ ] **Step 2: Add the `WatchProgress` model**

At the end of `app/models/attendance.py`:

```python
class WatchProgress(Base):
    """Per-user watch coverage for a recording, keyed by the recording's
    occurrence (zoom_uuid) + the real app user id. `watched_segments` is the
    merged union of actually-played spans — seeking to the end can't inflate it.
    """

    __tablename__ = "watch_progress"
    __table_args__ = (
        UniqueConstraint("zoom_uuid", "user_id", name="uq_watch_progress_identity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    zoom_uuid: Mapped[str] = mapped_column(String(255), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    last_position_secs: Mapped[float] = mapped_column(Float, default=0.0)
    max_position_secs: Mapped[float] = mapped_column(Float, default=0.0)
    watched_segments: Mapped[list] = mapped_column(JSON, default=list)
    duration_secs: Mapped[float] = mapped_column(Float, default=0.0)
    percent_complete: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 3: Add the `Float` import**

In the `from sqlalchemy import (...)` block at the top of `app/models/attendance.py`, add `Float` (keep alphabetical with the existing `DateTime, Integer, JSON, ...`).

- [ ] **Step 4: Verify import**

Run: `cd backend && python -c "from app.models.attendance import Meeting, WatchProgress; print(Meeting.recording_status.key, WatchProgress.__tablename__)"`
Expected: `recording_status watch_progress`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/attendance.py
git commit -m "feat(recordings): Meeting recording columns + WatchProgress model"
```

---

## Task 3: Alembic migration

**Files:**
- Create: `alembic/versions/<rev>_recording_watch_tracking.py`

- [ ] **Step 1: Autogenerate the migration**

Run (postgres must be up — `docker compose up -d postgres redis`):
```bash
cd backend && alembic revision --autogenerate -m "recording watch tracking" --rev-id rec0watch7m7a
```
Expected: a new file `alembic/versions/rec0watch7m7a_recording_watch_tracking.py` with `down_revision = "b8e3d6f1c742"`.

- [ ] **Step 2: Review the generated ops**

Open the file. Confirm `upgrade()` contains:
- `op.add_column("meetings", sa.Column("recording_s3_key", sa.String(512), nullable=True))`
- `op.add_column("meetings", sa.Column("recording_status", sa.String(16), nullable=False, server_default="none"))`
- `op.add_column("meetings", sa.Column("recording_duration_secs", sa.Integer(), nullable=True))`
- `op.create_table("watch_progress", ...)` with the unique constraint `uq_watch_progress_identity`.

If autogenerate omitted the `server_default="none"` (it often does for the model default), edit the `recording_status` column op to include `server_default="none"` so existing rows backfill. Then drop the server_default in a follow-up line is **not** needed — leaving it is fine.

- [ ] **Step 3: Apply + verify**

Run:
```bash
cd backend && alembic upgrade head && alembic current
```
Expected: head is `rec0watch7m7a`. Verify columns:
```bash
cd backend && python -c "
import asyncio; from sqlalchemy import text; from app.db.session import engine
async def go():
    async with engine.connect() as c:
        r = await c.execute(text(\"select column_name from information_schema.columns where table_name='watch_progress'\"))
        print(sorted(x[0] for x in r))
asyncio.run(go())"
```
Expected: includes `duration_secs, last_position_secs, max_position_secs, percent_complete, user_id, watched_segments, zoom_uuid`.

- [ ] **Step 4: Verify downgrade is clean**

Run: `cd backend && alembic downgrade -1 && alembic upgrade head`
Expected: no error (round-trips).

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/rec0watch7m7a_recording_watch_tracking.py
git commit -m "feat(recordings): migration — recording columns + watch_progress"
```

---

## Task 4: Heartbeat union core (pure, TDD)

The compliance heart. Pure function, no IO. Reuses `intervals.py`.

**Files:**
- Create: `app/utils/watch.py`
- Test: `tests/test_recording_heartbeat.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_recording_heartbeat.py`:

```python
"""Pure watch-coverage core: union of played spans, clamping, and the
compliance rule that seeking to the end yields partial — never 100%."""

from app.utils.watch import apply_heartbeat


def test_contiguous_play_accumulates():
    r = apply_heartbeat([], 0.0, 30.0, duration=100.0)
    assert r["segments"] == [[0.0, 30.0]]
    assert abs(r["percent_complete"] - 0.30) < 1e-9


def test_reconnect_overlap_unioned_not_summed():
    r = apply_heartbeat([[0.0, 30.0]], 20.0, 50.0, duration=100.0)
    assert r["segments"] == [[0.0, 50.0]]
    assert abs(r["percent_complete"] - 0.50) < 1e-9


def test_seek_to_end_yields_partial_not_full():
    # Watched 0–15, then dragged the scrubber to the end and watched 99–100.
    r = apply_heartbeat([[0.0, 15.0]], 99.0, 100.0, duration=100.0)
    assert r["segments"] == [[0.0, 15.0], [99.0, 100.0]]
    # 16s of 100s, NOT 100%.
    assert abs(r["percent_complete"] - 0.16) < 1e-9


def test_played_to_clamped_to_duration():
    # A bogus played_to beyond the recording length can't exceed 100%.
    r = apply_heartbeat([], 0.0, 999.0, duration=100.0)
    assert r["segments"] == [[0.0, 100.0]]
    assert r["percent_complete"] == 1.0


def test_negative_from_clamped_to_zero():
    r = apply_heartbeat([], -5.0, 10.0, duration=100.0)
    assert r["segments"] == [[0.0, 10.0]]


def test_zero_duration_is_zero_percent():
    r = apply_heartbeat([], 0.0, 10.0, duration=0.0)
    assert r["percent_complete"] == 0.0
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_recording_heartbeat.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.utils.watch'`.

- [ ] **Step 3: Implement `apply_heartbeat`**

Create `app/utils/watch.py`:

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && pytest tests/test_recording_heartbeat.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/utils/watch.py backend/tests/test_recording_heartbeat.py
git commit -m "feat(recordings): watch-coverage union core (seek-to-end != 100%)"
```

---

## Task 5: R2 storage helper

**Files:**
- Create: `app/utils/recording_storage.py`
- Test: `tests/test_recording_ingest.py` (the `pick_mp4` + `is_configured` slice)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_recording_ingest.py`:

```python
"""Recording ingest: MP4 selection, the 501 gate, and the ingest seam wiring."""

from app.utils.recording_storage import is_configured, pick_mp4


def test_pick_mp4_prefers_speaker_view():
    files = [
        {"file_type": "MP4", "recording_type": "audio_only", "id": "a"},
        {"file_type": "MP4", "recording_type": "shared_screen_with_speaker_view", "id": "b"},
        {"file_type": "M4A", "recording_type": "audio_only", "id": "c"},
    ]
    assert pick_mp4(files)["id"] == "b"


def test_pick_mp4_falls_back_to_any_mp4():
    files = [{"file_type": "MP4", "recording_type": "gallery_view", "id": "g"}]
    assert pick_mp4(files)["id"] == "g"


def test_pick_mp4_none_when_no_mp4():
    assert pick_mp4([{"file_type": "M4A", "id": "x"}]) is None
    assert pick_mp4([]) is None


def test_is_configured_false_without_creds(monkeypatch):
    from app.core import config
    for attr in ("R2_BUCKET", "R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        monkeypatch.setattr(config.settings, attr, "")
    assert is_configured() is False
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_recording_ingest.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.utils.recording_storage'`.

- [ ] **Step 3: Implement the helper**

Create `app/utils/recording_storage.py`:

```python
"""Cloudflare R2 (S3-compatible) storage for class recordings.

boto3 is sync; the API presigns inside a threadpool-friendly call and the
Celery ingest task is sync anyway. Everything raises `RuntimeError` when R2 is
unconfigured so callers can map that to a 501 / failed-ingest.
"""

from collections.abc import Iterator

import boto3
from botocore.config import Config

from app.core.config import settings

_MP4 = "MP4"
_PREFERRED = "shared_screen_with_speaker_view"


def is_configured() -> bool:
    return all(
        (
            settings.R2_BUCKET,
            settings.R2_ENDPOINT_URL,
            settings.R2_ACCESS_KEY_ID,
            settings.R2_SECRET_ACCESS_KEY,
        )
    )


def pick_mp4(recording_files: list[dict] | None) -> dict | None:
    """Speaker-view MP4 if present, else any MP4, else None."""
    mp4s = [
        f for f in (recording_files or [])
        if (f.get("file_type") or "").upper() == _MP4
    ]
    if not mp4s:
        return None
    for f in mp4s:
        if f.get("recording_type") == _PREFERRED:
            return f
    return mp4s[0]


def _client():
    if not is_configured():
        raise RuntimeError("R2 storage is not configured")
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def upload_stream(key: str, body: Iterator[bytes], content_type: str = "video/mp4") -> str:
    """Stream an iterator of bytes to R2 via the managed multipart uploader."""
    client = _client()

    class _Reader:
        def __init__(self, it: Iterator[bytes]):
            self._it = it
            self._buf = b""

        def read(self, n: int = -1) -> bytes:
            if n is None or n < 0:
                chunks = [self._buf, *self._it]
                self._buf = b""
                return b"".join(chunks)
            while len(self._buf) < n:
                try:
                    self._buf += next(self._it)
                except StopIteration:
                    break
            out, self._buf = self._buf[:n], self._buf[n:]
            return out

    client.upload_fileobj(
        _Reader(body),
        settings.R2_BUCKET,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return key


def presign_get(key: str, ttl_secs: int | None = None) -> str:
    """Short-lived presigned GET URL (works on R2 and AWS S3)."""
    client = _client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.R2_BUCKET, "Key": key},
        ExpiresIn=ttl_secs or settings.RECORDING_URL_TTL_SECS,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && pytest tests/test_recording_ingest.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/utils/recording_storage.py backend/tests/test_recording_ingest.py
git commit -m "feat(recordings): R2 storage helper (pick_mp4, presign, stream upload)"
```

---

## Task 6: Ingest Celery task (pure core + seams, TDD)

**Files:**
- Create: `app/workers/recording_tasks.py`
- Test: `tests/test_recording_ingest.py` (append the ingest-wiring tests)

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_recording_ingest.py`:

```python
import asyncio

from app.workers.recording_tasks import run_ingest


def _run(coro):
    return asyncio.run(coro)


def test_ingest_prefers_download_token_and_marks_stored():
    calls = {}

    async def get_token():
        calls["token_fetched"] = True
        return "s2s-token"

    async def http_get_stream(url):
        calls["url"] = url
        yield b"abc"
        yield b"def"

    async def upload(key, body):
        calls["key"] = key
        calls["bytes"] = b"".join([c async for c in body]) if hasattr(body, "__aiter__") else None
        return key

    async def mark(uuid, key, status, duration):
        calls["mark"] = (uuid, key, status, duration)

    files = [{
        "file_type": "MP4",
        "recording_type": "shared_screen_with_speaker_view",
        "download_url": "https://zoom.us/rec/abc.mp4",
        "recording_start": "2026-06-20T10:00:00Z",
        "recording_end": "2026-06-20T11:00:00Z",
    }]

    key = _run(run_ingest(
        "uuid-1", "dl-token", files,
        get_token=get_token, http_get_stream=http_get_stream, upload=upload, mark=mark,
    ))

    assert key == "recordings/uuid-1.mp4"
    # download_token preferred → S2S token never fetched
    assert "token_fetched" not in calls
    assert "access_token=dl-token" in calls["url"]
    assert calls["mark"] == ("uuid-1", "recordings/uuid-1.mp4", "stored", 3600)


def test_ingest_falls_back_to_s2s_when_no_download_token():
    async def get_token():
        return "s2s-token"

    async def http_get_stream(url):
        assert "access_token=s2s-token" in url
        yield b"x"

    async def upload(key, body):
        async for _ in body:
            pass
        return key

    marks = []

    async def mark(uuid, key, status, duration):
        marks.append((status, key))

    files = [{"file_type": "MP4", "recording_type": "gallery_view",
              "download_url": "https://zoom.us/rec/g.mp4"}]
    _run(run_ingest("u2", None, files,
                    get_token=get_token, http_get_stream=http_get_stream,
                    upload=upload, mark=mark))
    assert marks[-1][0] == "stored"


def test_ingest_marks_failed_when_no_mp4():
    marks = []

    async def mark(uuid, key, status, duration):
        marks.append((status, key))

    async def boom(*a, **k):  # must not be reached
        raise AssertionError("should not download")

    try:
        _run(run_ingest("u3", "t", [{"file_type": "M4A"}],
                        get_token=boom, http_get_stream=boom, upload=boom, mark=mark))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    assert marks == [("failed", None)]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_recording_ingest.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.workers.recording_tasks'`.

- [ ] **Step 3: Implement the task**

Create `app/workers/recording_tasks.py`:

```python
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
    async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                yield chunk


async def _default_upload(key: str, body: AsyncIterator[bytes]) -> str:
    # Bridge the async byte stream to the sync boto3 uploader off the event loop.
    chunks = [c async for c in body]
    await asyncio.to_thread(upload_stream, key, iter(chunks))
    return key


async def _default_mark(uuid: str, key: str | None, status: str, duration: int | None) -> None:
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
def ingest_recording(uuid: str, download_token: str | None, recording_files: list[dict]) -> str:
    return asyncio.run(run_ingest(uuid, download_token, recording_files))


def schedule_ingest(uuid: str, download_token: str | None, recording_files: list[dict]) -> None:
    """Enqueue the ingest job (best-effort; the webhook already acked)."""
    ingest_recording.apply_async(args=[uuid, download_token, recording_files])
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && pytest tests/test_recording_ingest.py -q`
Expected: PASS (7 passed).

> Note on the test seam: `_default_upload` materializes the async stream into a list before the threadpool call. The unit tests inject their own `upload`, so they exercise the wiring (token choice, url, mark) without boto3. The live multipart streaming is in `recording_storage.upload_stream` (Task 5).

- [ ] **Step 5: Commit**

```bash
git add backend/app/workers/recording_tasks.py backend/tests/test_recording_ingest.py
git commit -m "feat(recordings): seam-tested Zoom→R2 ingest Celery task"
```

---

## Task 7: Webhook `recording.completed` branch

**Files:**
- Modify: `app/api/webhooks.py`
- Test: `tests/test_webhooks.py` (append)

- [ ] **Step 1: Append the failing test**

Append to `tests/test_webhooks.py` (match the existing helpers in that file for signing — reuse `_signed_post`/`_headers` if present; otherwise mirror the existing signed-event test's setup):

```python
async def test_recording_completed_marks_pending_and_schedules(client, session, monkeypatch):
    import app.api.webhooks as wh

    scheduled = {}

    def fake_schedule(uuid, token, files):
        scheduled["args"] = (uuid, token, files)

    monkeypatch.setattr(wh.recording_tasks, "schedule_ingest", fake_schedule)

    body = {
        "event": "recording.completed",
        "event_ts": 1,
        "download_token": "dl-tok",
        "payload": {"object": {
            "uuid": "rec-uuid-1",
            "id": "82912345678",
            "topic": "DB Indexing",
            "recording_files": [
                {"file_type": "MP4", "recording_type": "shared_screen_with_speaker_view",
                 "download_url": "https://zoom.us/rec/x.mp4"}
            ],
        }},
    }
    # Reuse this test module's signed-POST helper:
    resp = await _post_signed(client, body)
    assert resp.status_code == 200

    from sqlalchemy import select
    from app.models.attendance import Meeting
    m = await session.scalar(select(Meeting).where(Meeting.zoom_uuid == "rec-uuid-1"))
    assert m is not None and m.recording_status == "pending"
    assert scheduled["args"][0] == "rec-uuid-1"
    assert scheduled["args"][1] == "dl-tok"
```

> If `tests/test_webhooks.py` names its signed-post helper differently, call that one instead of `_post_signed` and delete this note.

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_webhooks.py -k recording_completed -q`
Expected: FAIL (status not pending / `schedule_ingest` not called).

- [ ] **Step 3: Add the handler branch**

In `app/api/webhooks.py`, change the import:
```python
from app.workers import attendance_tasks, recording_tasks
```
In `_handle_event`, the `recording.completed` payload object carries `uuid` (no `meeting.` prefix), so add the branch **before** the `if not zoom_uuid and name.startswith("meeting.")` early-return is reached for recording events. Insert this branch in the `if/elif` chain:

```python
    elif name == "recording.completed":
        await _upsert_meeting(db, zoom_uuid, obj)
        meeting = await db.scalar(
            select(Meeting).where(Meeting.zoom_uuid == zoom_uuid)
        )
        if meeting is not None:
            meeting.recording_status = "pending"
        download_token = event.get("download_token") or (
            (event.get("payload") or {}).get("download_token")
        )
        recording_files = obj.get("recording_files") or []
        recording_tasks.schedule_ingest(zoom_uuid, download_token, recording_files)
```

Confirm the early-return guard at the top of `_handle_event` does not bail for recording events: it currently reads
```python
    if not zoom_uuid and name.startswith("meeting."):
        return
```
`recording.completed` does not start with `meeting.`, and `obj["uuid"]` is set, so the guard is not triggered — no change needed there.

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && pytest tests/test_webhooks.py -q`
Expected: PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/webhooks.py backend/tests/test_webhooks.py
git commit -m "feat(recordings): recording.completed webhook → mark pending + enqueue ingest"
```

---

## Task 8: Recording schemas

**Files:**
- Create: `app/schemas/recording.py`

- [ ] **Step 1: Create the schemas**

Create `app/schemas/recording.py`:

```python
"""Request/response models for recording playback + watch-tracking."""

from pydantic import BaseModel, Field


class RecordingUrlOut(BaseModel):
    url: str
    expires_in_secs: int


class HeartbeatIn(BaseModel):
    played_from: float = Field(ge=0)
    played_to: float = Field(ge=0)
    duration: float = Field(ge=0)


class ProgressOut(BaseModel):
    last_position_secs: float
    percent_complete: float
    segments: list[list[float]]


class WatchStatusOut(BaseModel):
    available: bool
    percent_complete: float
    last_position_secs: float
    duration_secs: float | None
```

- [ ] **Step 2: Verify import**

Run: `cd backend && python -c "from app.schemas.recording import HeartbeatIn, WatchStatusOut; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/recording.py
git commit -m "feat(recordings): playback + watch-tracking schemas"
```

---

## Task 9: Recordings API routes (session-scoped)

**Files:**
- Create: `app/api/recordings.py`
- Modify: `app/main.py`
- Test: `tests/test_recording_api.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_recording_api.py` (reuse the `_user`/`_login`/`_session_row`/`_enroll` helper style from `tests/test_live_join.py`):

```python
"""Session-scoped recording API: resolution, 404/501 gates, heartbeat union,
read-model shape, membership gating."""

from datetime import UTC, datetime

from app.auth.security import hash_password

_PW = "passphrase-1234"


async def _user(session, email, role="STUDENT"):
    from app.models.user import User, UserRole
    u = User(email=email, hashed_password=hash_password(_PW),
             display_name=email.split("@")[0], role=UserRole(role))
    session.add(u)
    await session.commit()
    return u.id


async def _login(client, email):
    client.cookies.clear()
    await client.post("/api/auth/login", json={"email": email, "password": _PW})


async def _seed(session, *, stored=True, zoom="82912345678", uuid="occ-1"):
    from app.models.course import ClassSession, Course, Enrollment, SessionStatus
    from app.models.attendance import Meeting
    session.add(Course(id="c1", title="DB"))
    await session.flush()
    session.add(ClassSession(
        id="s1", course_id="c1", host_id="h1", title="Live",
        scheduled_at=datetime(2026, 7, 1, 10, tzinfo=UTC),
        duration_mins=60, zoom_meeting_id=zoom, status=SessionStatus.ENDED,
    ))
    m = Meeting(zoom_uuid=uuid, zoom_meeting_id=zoom,
                ended_at=datetime(2026, 7, 1, 11, tzinfo=UTC))
    if stored:
        m.recording_s3_key = f"recordings/{uuid}.mp4"
        m.recording_status = "stored"
        m.recording_duration_secs = 100
    session.add(m)
    await session.commit()


async def _enroll(session, user_id):
    from app.models.course import Enrollment
    session.add(Enrollment(user_id=user_id, course_id="c1"))
    await session.commit()


async def test_url_501_when_r2_unconfigured(client, session, monkeypatch):
    import app.api.recordings as rec
    # Recording row is 'stored', but R2 creds are absent → 501 (not 404).
    monkeypatch.setattr(rec, "is_configured", lambda: False)
    uid = await _user(session, "a@x.com"); await _enroll(session, uid)
    await _seed(session)
    await _login(client, "a@x.com")
    r = await client.get("/api/sessions/s1/recording/url")
    assert r.status_code == 501


async def test_url_404_when_no_recording(client, session, monkeypatch):
    import app.api.recordings as rec
    monkeypatch.setattr(rec, "is_configured", lambda: True)
    uid = await _user(session, "a@x.com"); await _enroll(session, uid)
    await _seed(session, stored=False)
    await _login(client, "a@x.com")
    r = await client.get("/api/sessions/s1/recording/url")
    assert r.status_code == 404


async def test_url_presigns_when_configured(client, session, monkeypatch):
    import app.api.recordings as rec
    monkeypatch.setattr(rec, "is_configured", lambda: True)
    monkeypatch.setattr(rec, "presign_get", lambda key, ttl: f"https://signed/{key}?t={ttl}")
    uid = await _user(session, "a@x.com"); await _enroll(session, uid)
    await _seed(session)
    await _login(client, "a@x.com")
    r = await client.get("/api/sessions/s1/recording/url")
    assert r.status_code == 200
    assert r.json()["url"].startswith("https://signed/recordings/occ-1.mp4")


async def test_heartbeat_seek_to_end_partial_and_read_model(client, session):
    uid = await _user(session, "a@x.com"); await _enroll(session, uid)
    await _seed(session)
    await _login(client, "a@x.com")
    # watch 0–15
    r = await client.post("/api/sessions/s1/recording/heartbeat",
                          json={"played_from": 0, "played_to": 15, "duration": 100})
    assert r.status_code == 200
    # seek to end, watch 99–100 → 16%, not 100%
    r = await client.post("/api/sessions/s1/recording/heartbeat",
                          json={"played_from": 99, "played_to": 100, "duration": 100})
    assert abs(r.json()["percent_complete"] - 0.16) < 1e-9
    # read-model
    ws = await client.get("/api/sessions/s1/recording/watch-status")
    body = ws.json()
    assert body["available"] is True
    assert abs(body["percent_complete"] - 0.16) < 1e-9
    assert body["last_position_secs"] == 100
    assert body["duration_secs"] == 100


async def test_heartbeat_uses_server_duration_over_client(client, session):
    # server duration is 100; a lying client says duration=20 → still /100.
    uid = await _user(session, "a@x.com"); await _enroll(session, uid)
    await _seed(session)
    await _login(client, "a@x.com")
    r = await client.post("/api/sessions/s1/recording/heartbeat",
                          json={"played_from": 0, "played_to": 20, "duration": 20})
    assert abs(r.json()["percent_complete"] - 0.20) < 1e-9  # 20/100, not 20/20


async def test_non_member_forbidden(client, session):
    await _user(session, "owner@x.com")
    await _seed(session)
    await _user(session, "stranger@x.com")
    await _login(client, "stranger@x.com")
    r = await client.get("/api/sessions/s1/recording/progress")
    assert r.status_code == 403
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_recording_api.py -q`
Expected: FAIL — 404 from FastAPI (routes not registered).

- [ ] **Step 3: Implement the routes**

Create `app/api/recordings.py`:

```python
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

    clamped_to = min(max(body.played_to, 0.0), duration) if duration > 0 else body.played_to
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
            available=False, percent_complete=0, last_position_secs=0, duration_secs=None
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
```

- [ ] **Step 4: Register the router**

In `app/main.py`: add `recordings` to the `from app.api import (...)` tuple (line ~72), and add after the `webhooks` include (line ~91):

```python
    app.include_router(recordings.router, prefix="/api")
```

- [ ] **Step 5: Run to verify pass**

Run: `cd backend && pytest tests/test_recording_api.py -q`
Expected: PASS (6 passed).

- [ ] **Step 6: Full backend gate**

Run: `cd backend && ruff check . && ruff format --check . && pytest -q`
Expected: all green (existing + new ~17 new tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/recordings.py backend/app/main.py backend/tests/test_recording_api.py
git commit -m "feat(recordings): session-scoped playback + watch-tracking API"
```

---

## Task 10: Frontend hooks

**Files:**
- Create: `frontend/src/hooks/useRecording.ts`

- [ ] **Step 1: Implement the hooks**

Create `frontend/src/hooks/useRecording.ts`:

```ts
import { useMutation, useQuery } from '@tanstack/react-query'

import { api, ApiError } from '@/lib/api'

export interface RecordingUrl {
  url: string
  expiresInSecs: number
}
export interface Progress {
  lastPositionSecs: number
  percentComplete: number
  segments: number[][]
}
export interface WatchStatus {
  available: boolean
  percentComplete: number
  lastPositionSecs: number
  durationSecs: number | null
}
export interface HeartbeatBody {
  playedFrom: number
  playedTo: number
  duration: number
}

// The backend serializes snake_case; map to camelCase at the edge.
function camelProgress(p: any): Progress {
  return {
    lastPositionSecs: p.last_position_secs,
    percentComplete: p.percent_complete,
    segments: p.segments ?? [],
  }
}

export function useRecordingUrl(sessionId: string) {
  return useQuery({
    queryKey: ['recording', sessionId, 'url'],
    queryFn: async () => {
      const r = await api.get<any>(`/api/sessions/${sessionId}/recording/url`)
      return { url: r.url, expiresInSecs: r.expires_in_secs } as RecordingUrl
    },
    retry: (count, err) =>
      // don't retry the expected "not available / not configured" states
      !(err instanceof ApiError && [404, 501].includes(err.status)) && count < 2,
  })
}

export function useRecordingProgress(sessionId: string) {
  return useQuery({
    queryKey: ['recording', sessionId, 'progress'],
    queryFn: async () =>
      camelProgress(await api.get<any>(`/api/sessions/${sessionId}/recording/progress`)),
  })
}

export function useHeartbeat(sessionId: string) {
  return useMutation({
    mutationFn: async (b: HeartbeatBody) =>
      camelProgress(
        await api.post<any>(`/api/sessions/${sessionId}/recording/heartbeat`, {
          played_from: b.playedFrom,
          played_to: b.playedTo,
          duration: b.duration,
        }),
      ),
  })
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc -b --noEmit` (or `npm run build` if tsc-only is not wired)
Expected: no errors from `useRecording.ts`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useRecording.ts
git commit -m "feat(recordings): frontend recording hooks (url/progress/heartbeat)"
```

---

## Task 11: RecordingPlayerPage + route

**Files:**
- Create: `frontend/src/pages/RecordingPlayerPage.tsx`
- Modify: `frontend/src/router.tsx`

- [ ] **Step 1: Implement the player**

Create `frontend/src/pages/RecordingPlayerPage.tsx` — a faithful port of `testing/src/RecordingPlayer.tsx`'s span logic (do NOT simplify to `[0, currentTime]`); identity is the cookie session (no `x-user-id`), URLs are session-scoped, and it uses the hooks from Task 10:

```tsx
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError } from '@/lib/api'
import { useHeartbeat, useRecordingProgress, useRecordingUrl } from '@/hooks/useRecording'

const HEARTBEAT_MS = 10_000

export default function RecordingPlayerPage() {
  const { sessionId = '' } = useParams()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [percent, setPercent] = useState(0)

  const urlQ = useRecordingUrl(sessionId)
  const progressQ = useRecordingProgress(sessionId)
  const heartbeat = useHeartbeat(sessionId)

  // span tracking — exactly the prototype's contiguous-play logic
  const spanStart = useRef<number | null>(null)
  const lastTime = useRef(0)
  const resumeAt = progressQ.data?.lastPositionSecs ?? 0

  useEffect(() => {
    if (progressQ.data) setPercent(progressQ.data.percentComplete)
  }, [progressQ.data])

  const flush = useCallback(
    (reason: string) => {
      const v = videoRef.current
      if (!v || spanStart.current == null) return
      const from = spanStart.current
      const to = lastTime.current
      spanStart.current = v.paused ? null : v.currentTime
      if (to - from < 0.5) return
      heartbeat.mutate(
        { playedFrom: from, playedTo: to, duration: v.duration || 0 },
        { onSuccess: (p) => setPercent(p.percentComplete) },
      )
      void reason
    },
    [heartbeat],
  )

  useEffect(() => {
    const id = setInterval(() => flush('interval'), HEARTBEAT_MS)
    const onUnload = () => flush('unload')
    window.addEventListener('pagehide', onUnload)
    return () => {
      clearInterval(id)
      window.removeEventListener('pagehide', onUnload)
      flush('unmount')
    }
  }, [flush])

  const onLoadedMetadata = () => {
    if (resumeAt > 0 && videoRef.current) videoRef.current.currentTime = resumeAt
  }
  const onPlay = () => {
    if (videoRef.current) spanStart.current = videoRef.current.currentTime
  }
  const onTimeUpdate = () => {
    if (videoRef.current && !videoRef.current.seeking)
      lastTime.current = videoRef.current.currentTime
  }
  const onSeeking = () => flush('seek')
  const onSeeked = () => {
    if (videoRef.current && !videoRef.current.paused)
      spanStart.current = videoRef.current.currentTime
  }
  const onPause = () => flush('pause')
  const onEnded = () => flush('ended')

  const notAvailable =
    urlQ.error instanceof ApiError && urlQ.error.status === 404
  const notConfigured =
    urlQ.error instanceof ApiError && urlQ.error.status === 501

  return (
    <div className="mx-auto max-w-4xl p-6">
      <Link to={`/session/${sessionId}`} className="text-sm text-text-link">
        ← Back to session
      </Link>
      <h1 className="mt-2 text-xl font-semibold text-text-primary">
        Recording — {(percent * 100).toFixed(1)}% watched
      </h1>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-border">
        <div
          className="h-full bg-text-link transition-[width]"
          style={{ width: `${Math.min(100, percent * 100)}%` }}
        />
      </div>

      <div className="mt-4">
        {urlQ.isLoading && <p className="text-text-muted">Loading recording…</p>}
        {notAvailable && (
          <p className="text-text-muted">No recording is available for this session yet.</p>
        )}
        {notConfigured && (
          <p className="text-text-muted">Recording playback is not configured on this server.</p>
        )}
        {urlQ.data && (
          <video
            ref={videoRef}
            src={urlQ.data.url}
            controls
            crossOrigin="anonymous"
            className="w-full rounded-card bg-black"
            onLoadedMetadata={onLoadedMetadata}
            onPlay={onPlay}
            onTimeUpdate={onTimeUpdate}
            onSeeking={onSeeking}
            onSeeked={onSeeked}
            onPause={onPause}
            onEnded={onEnded}
          />
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Register the route**

In `frontend/src/router.tsx`: add the lazy import next to the others:
```tsx
const RecordingPlayerPage = lazy(() => import('@/pages/RecordingPlayerPage'))
```
and inside the `ProtectedRoute` children array, after the `/live/:sessionId` entry:
```tsx
      { path: '/session/:sessionId/recording', element: <Lazy><RecordingPlayerPage /></Lazy> },
```

- [ ] **Step 3: Build gate**

Run: `cd frontend && npm run build`
Expected: `tsc -b` + `vite build` succeed.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/RecordingPlayerPage.tsx frontend/src/router.tsx
git commit -m "feat(recordings): compliance-grade RecordingPlayer page + route"
```

---

## Task 12: Wire the dashboard seam (minimal, non-invasive)

Make `VideoCard`'s "Resume" point at the real player + show watch %. This is the Dev A seam — keep it minimal and flagged.

**Files:**
- Modify: `frontend/src/components/dashboard/VideoCard.tsx`

- [ ] **Step 1: Link Resume to the player**

In `VideoCard.tsx`, change the wrapping `<Link to={`/session/${session.id}`}>` to `to={`/session/${session.id}/recording`}` so "Continue Watching" opens the player directly.

- [ ] **Step 2: Build gate**

Run: `cd frontend && npm run build`
Expected: green.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/dashboard/VideoCard.tsx
git commit -m "feat(recordings): Continue Watching opens the recording player"
```

> **Seam note for Dev A:** a richer progress bar on the card can consume
> `GET /api/sessions/{id}/recording/watch-status` (`{available, percentComplete,
> lastPositionSecs, durationSecs}`). Left as Dev A's dashboard polish.

---

## Task 13: Real end-to-end verification (the anti-dummy gate)

Needs your Cloudflare R2 creds. Not a CI step — a manual proof that playback +
watch-tracking work against real storage.

- [ ] **Step 1: Provision + configure R2**

Create an R2 bucket + API token; set `R2_ACCOUNT_ID/ACCESS_KEY_ID/SECRET_ACCESS_KEY/BUCKET/ENDPOINT_URL` in `backend/.env`. Apply bucket CORS allowing the app origin, allowing the `Range` request header, and exposing `Content-Range, Accept-Ranges, Content-Length` (per spec §8.1).

- [ ] **Step 2: Seed a real recording**

Upload a real MP4 to `recordings/e2e-1.mp4` in the bucket. Insert/point a `Meeting`:
```bash
cd backend && python -c "
import asyncio; from datetime import UTC, datetime
from app.db.session import AsyncSessionLocal
from app.models.attendance import Meeting
from app.models.course import ClassSession, Course, SessionStatus
async def go():
    async with AsyncSessionLocal() as db:
        db.add(Course(id='c-e2e', title='E2E'))
        db.add(ClassSession(id='s-e2e', course_id='c-e2e', host_id='h', title='E2E',
            scheduled_at=datetime(2026,6,20,10,tzinfo=UTC), duration_mins=60,
            zoom_meeting_id='99900099', status=SessionStatus.ENDED))
        db.add(Meeting(zoom_uuid='e2e-1', zoom_meeting_id='99900099',
            ended_at=datetime(2026,6,20,11,tzinfo=UTC),
            recording_s3_key='recordings/e2e-1.mp4', recording_status='stored',
            recording_duration_secs=int(<<REAL_MP4_DURATION_SECS>>)))
        await db.commit()
asyncio.run(go())"
```
(Replace `<<REAL_MP4_DURATION_SECS>>` with the actual file length; enroll your user in `c-e2e` or log in as host/admin.)

- [ ] **Step 2.5: Local proxy headers note**

Vite dev serves the player under COOP/COEP (from `vite.config.ts`); the cross-origin `<video crossOrigin="anonymous">` will only load if Step 1's R2 CORS is correct. If the video element stays blank, check the browser console for a COEP/CORS block — that's the §8 trap, not a code bug.

- [ ] **Step 3: Verify in the browser**

Run backend (`uvicorn app.main:socket_app --reload --port 8000`) + frontend (`npm run dev`), open `/session/s-e2e/recording`. Confirm:
1. Video loads from the presigned R2 URL.
2. **Seeking works** (drag the scrubber — Range requests succeed).
3. Play 0→N linearly, reload → resumes near N, % climbs.
4. Reload fresh, **seek to the end and play the last few seconds** → % stays low (partial), NOT ~100%. This is the compliance proof.
5. `GET /api/sessions/s-e2e/recording/watch-status` reflects the %.

- [ ] **Step 4: Record the result**

Note the observed behavior (esp. #4 and the seek/Range check) in the PR description, mirroring how M5/M6 documented their verification.

---

## Self-Review notes (done at authoring)

- **Spec coverage:** §3 model → T2/T3; §4 ingest → T5/T6/T7; §5 API → T8/T9; §6 player → T10/T11; §4 read-model → T9 `watch-status` + T12 seam; §8 deploy/COEP/Range/env → T1 + T11 (`crossOrigin`, presigned not proxied) + T13; §9 tests → T4/T6/T7/T9 + T13; §7 known issues recorded in spec.
- **Type consistency:** `apply_heartbeat` returns `{segments, percent_complete}` (T4) — consumed identically in T9. Backend snake_case (`percent_complete`, `last_position_secs`, `expires_in_secs`) mapped to camelCase once at the hook edge (T10); player uses camelCase only.
- **Server-authoritative duration:** enforced in T9 heartbeat (Meeting duration wins) and asserted in `test_heartbeat_uses_server_duration_over_client`.
- **No bytes proxied through FastAPI:** playback is a presigned redirect URL handed to the client (T9), preserving Range for seeking (§8.3).
```
