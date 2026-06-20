# SESSION HANDOFF — linkHQ

_Living status doc. Update before ending a long session; read it to resume._
_Last updated: 2026-06-21._

## Where things stand

### ✅ Done and on `origin/main`
- **M7 — Recording ingest + watch-tracking** (Dev B). Backend (webhooks →
  ingest → R2 storage → session-scoped playback/heartbeat/watch-status) +
  frontend recording player. 184 backend tests + frontend build green.
- **Integration**: M7 was rebased cleanly onto the partner's admin/enrollment
  work; `main` is the single source of truth.
- **Deploy is LIVE** at https://linkhq.onrender.com (Render, free tier — sleeps
  when idle, first request wakes it in ~30–60s). `/health` ok, DB ready, all
  recording API routes serving. The Render service now builds **`main`**
  (`render.yaml` pins `branch: main`).
- **Seed fix**: seed is idempotent by **email** (a legacy-id row was crashing the
  deploy with `duplicate key ix_users_email`). Fixed + regression-tested.

### 🔄 Pending — committed code, NOT yet pushed (uncommitted in working tree)
1. **Visible demo recording** so M7 is click-through on the live site without R2:
   - `backend/app/api/recordings.py` — `/recording/url` serves an external
     `http(s)` key as-is (CDN-hosted recordings), not only presigned R2.
   - `backend/scripts/seed.py` — seeds a public, COEP-safe demo MP4 onto the 3
     past sessions, on every deploy.
   - `backend/tests/test_recording_api.py` — passthrough test. Suite: 185 green.
   - Verified locally: `/recording/url` for `seed-session-past-1` returns the MP4.
2. **Context hygiene** (this batch): slim root `CLAUDE.md` + `backend/CLAUDE.md`
   + `frontend/CLAUDE.md`, `.claudeignore`, this file.

### ⏳ Not started / needs the user
- **T13 — real R2 recordings**: needs a Cloudflare R2 bucket + token (+ optional
  Zoom cloud recording for auto-ingest). Runbook: `docs/runbooks/m7-recording-r2.md`.
  The demo recording above proves the whole player/heartbeat/watch-% pipeline
  works on the live site in the meantime.
- **M8+** (post-meeting AI, analytics) — future milestones, not begun.

## How to SEE the app working
1. Open https://linkhq.onrender.com (wait for it to wake).
2. Log in — demo users, password `password123`:
   `instructor@linkhq.dev` (admin/instructor) · `student1@linkhq.dev` (student).
3. Dashboard → **Continue Watching** → click a **Past Lecture** → the recording
   player opens; the video plays, "% watched" climbs, and seeking to the end
   keeps the % partial (the compliance watch-tracking). _← appears after the
   pending demo-recording commit is pushed + redeployed._

## Next action
Push the pending commits → Render auto-redeploys `main` → `start.sh` re-seeds →
demo recordings appear. Commit commands are in the chat; nothing is committed yet
(the repo owner runs git).

## Key facts
- Deploy entrypoint: `backend/start.sh` (migrate → seed → celery worker → uvicorn).
- Serve `app.main:socket_app` (not `app`). COOP/COEP needed for the Zoom SDK.
- Compliance primitive: `backend/app/utils/intervals.py` (union of intervals).
