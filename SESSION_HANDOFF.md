# SESSION HANDOFF — nodeLive

_Living status doc. Update before ending a long session; read it to resume._
_Last updated: 2026-06-22._

## Deployment
- **Live:** https://nodelive.onrender.com (Render free tier — sleeps when idle,
  first request wakes it ~30–60s; OOMs past ~15 concurrent users).
- Builds `main` via Docker; auto-deploys on push. `start.sh`: alembic → seed (bg)
  → Celery beat + worker (`solo` pool) → uvicorn `app.main:socket_app`.
- Demo logins (password `password123`): `instructor@nodelive.dev` (host/admin),
  `student1@nodelive.dev`, `student2@nodelive.dev`.

## ✅ Done 2026-06-22 (attendance pipeline + reliability, on `main`)
- **Attendance pipeline repaired end-to-end** — sessions now flip to `ENDED`
  (webhook `meeting.ended`, admin "End Session" button, or hourly `sessions.janitor`
  for stale `LIVE`); `ClassSession.ended_at` added (migration). Reconcile only runs
  on `ENDED`. Admin Attendance tab + `SyncAttendance` (webhook-independent manual
  reconcile that refreshes the Zoom token first so new scopes apply instantly).
- **Free-Zoom-plan fallback** — reconcile degrades Reports API → `past_meetings`
  → webhook participant log (`AttendanceSession`), same interval-union math, so
  attendance computes without a paid Zoom plan. Reconcile task auto-retries (5×,
  backoff).
- **Reliability** — Redis-backed Zoom S2S token cache (shared web+worker, in-proc
  fallback); `celery beat` now started in `start.sh` (was worker-only); webhook
  errors logged not swallowed; org-scoped admin queries; LIVE dashboard badges.
- **Groq LLM fallback WIRED** (was the open item below) — `app/utils/llm.py`
  `stream_chat` is Anthropic-primary, Groq fallback (OpenAI SSE via httpx); `live.py`
  uses it. AI is 501 only when **neither** key is set.

## ✅ Done 2026-06-21 (all on `main`, live-verified)
- **M7 Recording ingest + watch-tracking** — webhook→ingest→R2 storage, session-
  scoped playback/heartbeat/watch-status, `RecordingPlayerPage`. Seek-to-end ≠ 100%.
  Runbook: `docs/runbooks/m7-recording-r2.md`.
- **Live Zoom meetings (S2S auto-create + host ZAK)** — host's "Join video"
  auto-creates a real Zoom meeting + gets the ZAK to start it; everyone else joins
  as a named participant; host-start flips the session **LIVE**; students see
  "Waiting for the host…" then **auto-enter**. Verified host+student in a browser.
- **Fixes:** socket.io prod-origin CORS (403); single-host ZAK (no duplicate
  identity); assign any member as host; idempotent seed (email-keyed) + enrollment
  backfill; dashboard auto-refresh; free-tier memory trim (solo worker); deploy
  polish (HEAD / → 200, bg seed).
- **Docs synced** (this run): all milestone + branch docs marked to real state;
  `plan.md` §7.4a documents the **Anthropic→Groq LLM fallback**.

## 🐞 Code audit 2026-06-22 — bugs found and FIXED (TDD, on `main`)
_All confirmed against code, fixed test-first. Backend gate green (ruff + format +
pytest); `npm run build` green. Local pytest needs `ZOOM_SDK_KEY`/`SECRET` (CI
injects dummies in `ci.yml:54`, else `test_live_join` 503s — non-product)._

- ✅ **P0 BLOCKER — Attendance showed zeros even after a perfect reconcile.**
  Identity was off by one char: SDK sends `customerKey = user.id.slice(0,35)`
  (`useZoomSDK.ts:129`), stored verbatim in `AttendanceFinal.user_id`, but the read
  matched the full 36-char `User.id`. **Fixed** in `admin.py` `session_attendance`:
  match on full id → `u.id[:35]` prefix → email (also repairs already-stored rows).
- ✅ **P0 MAJOR — Email-only attendees invisible.** Read filtered
  `user_id.is_not(None)`, dropping free-plan/guest finals. **Fixed** in the same
  read (now matches finals by email too).
- ✅ **MAJOR — Recording ingest never ran.** `recording_tasks` wasn't in
  `celery_app.py` `include`, so the worker never registered `recording.ingest`.
  **Fixed** (added to `include`; test asserts membership). Still needs `R2_*` set
  to actually store.
- ✅ **Socket `join_session` had no enrollment check.** **Fixed**: extracted
  `authorize_join` (`realtime/server.py`) — non-privileged users must be enrolled
  before entering broadcast rooms. (No behaviour change in single-org; closes the
  multi-org leak.)
- ✅ **Janitor didn't trigger reconcile.** **Fixed**: `_run_janitor` now schedules
  reconcile for each auto-ended session's meeting UUIDs.
- ✅ **`meeting.ended` no-op'd without a prior Meeting row.** **Fixed**: the
  handler upserts the meeting from the ended payload's `id` before flipping.

**⬜ Still open (deliberately not done):**
- **`list_all_sessions` org-scoping** (production-fixes.md Fix 7). Can't be done
  cleanly — `Course` has **no `org_id`** (single-org design), so a real org filter
  needs a schema change first. Harmless today (single org). Left as a multi-org
  TODO rather than shipping a fragile enrolled-members filter.

**Doc-accuracy fixes (claims that are now stale):**
- `docs/production-fixes.md` reads as an open plan; really 11/12 done — **Fix 7 not
  done**, Fixes 3 & 11 (frontend) done.
- `docs/milestones-dashboard.md` says assignment submission upload is "not
  implemented"; it **is** (`assignments.py:185-253`, presign PUT/GET, 501 only when
  R2 unset).
- "Enrollment backfill on login" is stale — only signup + course-create backfill
  (`auth.py:91`, `admin.py:291`); login does not.

## 🔑 Required prod env (Render dashboard, `sync:false`)
Set + working: `ZOOM_SDK_KEY/SECRET`, `ZOOM_S2S_ACCOUNT_ID/CLIENT_ID/CLIENT_SECRET`,
`ZOOM_HOST_EMAIL` (S2S scopes: `meeting:write:meeting:admin`, `meeting:read:meeting:admin`,
`user:read:token:admin`). **AI:** set **either** `ANTHROPIC_API_KEY` **or**
`GROQ_API_KEY` (+ `GROQ_MODEL`) — the fallback is wired, AI is 501 only if neither
is set. **Not set:** `R2_*` (→ recording playback 501; demo recording is seeded).
Attendance reconcile auto-degrades to the webhook log on a free Zoom plan (no
`report:read:*` scope needed for that path).

## ⬜ Not started / next
- **M8** post-meeting AI pipeline (transcript→summary→notes→auto-quiz), **M9** AI
  recommendations/analytics.
- **MP** hardening: **paid Render Starter (2GB) + dedicated worker** for the
  50-device demo (free tier OOMs); Sentry, k6 load test, GH Actions deploy.

## Key facts
- Serve `app.main:socket_app` (not `app`). COOP/COEP needed for the Zoom SDK.
- Compliance primitive: `backend/app/utils/intervals.py` (union of intervals).
- `is_zoom_host = (user.id == cs.host_id)` — only the session host gets the ZAK.
