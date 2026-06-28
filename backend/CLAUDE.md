# CLAUDE.md — backend (nodeLive API)

Python 3.12 · FastAPI · python-socketio (ASGI) · SQLAlchemy 2.0 async + Alembic ·
Celery + Redis · python-jose JWT (HttpOnly cookie) + passlib Argon2id · Anthropic.

## Commands (run from `backend/`)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                  # Zoom + Anthropic + R2 creds
alembic upgrade head
uvicorn app.main:socket_app --reload --port 8000   # socket_app, NOT app
ruff check . && ruff format --check .  # lint gate (CI)
pytest                                 # needs postgres up; conftest auto-creates nodelive_test
```
Tests live in `tests/`; ruff + pytest config in `pyproject.toml`. Shell env does
not persist between one-off commands — prefix with `source .venv/bin/activate &&`.

## Critical gotchas
- **Serve `app.main:socket_app`** (wraps FastAPI + socket.io) or WebSockets 404.
- **Webhook HMAC is over raw bytes** — read the raw request body for the `v0`
  SHA-256 check; parsing JSON first changes the bytes and breaks verification.
- **Reports API needs the meeting UUID, not the numeric id** (numeric returns the
  wrong instance for recurring meetings); UUIDs containing `/` are double-encoded.
- **Recording download URLs are 401 without auth** — append the webhook
  `download_token`, else an S2S OAuth token.
- **Importing `app.main` doesn't open the DB** (asyncpg connects lazily); `/health`
  has no deps, `/health/ready` pings the DB.
- **Test DB ownership**: `nodelive_test` is auto-created by `conftest` as the
  `DATABASE_URL` user — if it was created by a different role you get
  `permission denied for schema public`; drop it and let conftest recreate it.

## The compliance primitive (don't duplicate)
`app/utils/intervals.py` (`merge_intervals` / `coverage_fraction`) = credit from
the **union of real intervals**. Used by attendance reconcile
(`app/workers/attendance_tasks.py`) AND watch-tracking (`app/utils/watch.py` +
`app/api/recordings.py`). Rule encoded in tests: **seek-to-end yields partial,
not 100%**. Keep its tests.

## Identity glue
`customerKey` (= `user.id[:35]`) flows SDK join → webhook
`participant.customer_key` → Reports API, so attendance attributes to a real user.
**Email is the fallback match key** (customer_key is absent for guests).

## Attendance lifecycle + reconcile fallback
- **Reconcile only runs on `ENDED` sessions.** `ClassSession.status` flips to
  `ENDED` (and stamps `ended_at`) three ways: the `meeting.ended` webhook
  (`_mark_ended`), `POST /admin/sessions/{id}/end`, or the hourly `sessions.janitor`
  Celery task (`app/workers/session_tasks.py`) that auto-ends `LIVE` sessions older
  than 2h. The janitor needs **`celery beat`** running — `start.sh` launches it
  alongside the worker; `beat_schedule` lives in `celery_app.py`.
- **Reconcile degrades for free Zoom plans** (`attendance_tasks.py`): the Reports
  API (`/report/meetings`, richest, carries `customer_key`) needs `report:read:*`
  + a paid plan. On a 400/401/403 it falls back to `/past_meetings` (lighter scope,
  email-match), then to `reconcile_from_webhook_log` (the `AttendanceSession`
  webhook log — works on any plan). All three feed the same `reconcile_participants`
  union math. The task auto-retries (5×, exponential backoff) transient errors.
- **`POST /admin/sessions/{id}/sync-attendance`** is the webhook-independent manual
  path — refreshes the Zoom token first (so newly-granted scopes apply instantly),
  then reconciles on demand. Admin Attendance tab is driven by this + `GET
  /sessions/{id}/attendance`.
- Zoom S2S token is cached in **Redis** (shared across web + worker, survives
  restart) with an in-process fallback — `app/utils/zoom_auth.py`.

## Recordings (M7)
- Ingest: `recording.completed` webhook → `app/workers/recording_tasks.py`
  (Celery) → download MP4 → stream to R2 (`app/utils/recording_storage.py`,
  boto3 S3 API). Pure core behind injection seams; live path needs real creds.
- Playback: `app/api/recordings.py` session-scoped routes. Returns a presigned R2
  GET URL, **or** an external `http(s)` key served as-is; **501 when R2
  unconfigured** (graceful degrade).
- Watch %: `watch_progress` table, union via `intervals.py`; `watch-status`
  read-model for the dashboard.
- R2 setup + end-to-end verification: `docs/runbooks/m7-recording-r2.md`.

## Seed + deploy
`scripts/seed.py` runs on every deploy (`start.sh`: alembic → seed → celery →
uvicorn). It is idempotent — **look users up by EMAIL** (the unique key), not by
id, or a re-seed on a legacy DB throws `duplicate key ... ix_users_email`. A
public demo recording is seeded so the player is click-through visible without R2.

## LLM provider (dual)
`app/utils/llm.py` `stream_chat` is Anthropic-primary, **Groq fallback** (OpenAI
SSE protocol, parsed via httpx — no SDK). Used by `live.py` AI chat. Falls back to
Groq when `ANTHROPIC_API_KEY` is unset *or* an Anthropic call fails before emitting
output. AI is 501 only when **neither** key is set (`is_configured()`).

## Known incomplete (intentional)
- Zoom S2S OAuth + R2 ingest are wired to `.env` but only seam-tested offline
  (live paths need real creds). `app/utils/zoom_auth.py` raises until `ZOOM_S2S_*`
  is set; recording playback returns 501 until `R2_*` is set.
