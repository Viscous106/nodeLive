# SESSION HANDOFF — linkHQ

_Living status doc. Update before ending a long session; read it to resume._
_Last updated: 2026-06-21._

## Deployment
- **Live:** https://linkhq.onrender.com (Render free tier — sleeps when idle,
  first request wakes it ~30–60s; OOMs past ~15 concurrent users).
- Builds `main` via Docker; auto-deploys on push. `start.sh`: alembic → seed (bg)
  → Celery worker (`solo` pool) → uvicorn `app.main:socket_app`.
- Demo logins (password `password123`): `instructor@linkhq.dev` (host/admin),
  `student1@linkhq.dev`, `student2@linkhq.dev`.

## ✅ Done this run (all on `main`, live-verified)
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

## 🔑 Required prod env (Render dashboard, `sync:false`)
Set + working: `ZOOM_SDK_KEY/SECRET`, `ZOOM_S2S_ACCOUNT_ID/CLIENT_ID/CLIENT_SECRET`,
`ZOOM_HOST_EMAIL` (S2S scopes: `meeting:write:meeting:admin`, `meeting:read:meeting:admin`,
`user:read:token:admin`). **Not set:** `ANTHROPIC_API_KEY` (→ AI is 501 until set,
or wire Groq), `R2_*` (→ recording playback 501; demo recording is seeded).

## ⬜ Not started / next
- **Groq LLM fallback** — documented (`plan.md` §7.4a, config `GROQ_API_KEY`/`GROQ_MODEL`);
  **code not wired** — `live.py`'s AI chat still calls Anthropic only. Implement the
  `chat()` wrapper so AI works via Groq without an Anthropic key.
- **M8** post-meeting AI pipeline (transcript→summary→notes→auto-quiz), **M9** AI
  recommendations/analytics. Dev A: admin **Attendance + Overview** tabs.
- **MP** hardening: **paid Render Starter (2GB) + dedicated worker** for the
  50-device demo (free tier OOMs); Sentry, k6 load test, GH Actions deploy.

## Key facts
- Serve `app.main:socket_app` (not `app`). COOP/COEP needed for the Zoom SDK.
- Compliance primitive: `backend/app/utils/intervals.py` (union of intervals).
- `is_zoom_host = (user.id == cs.host_id)` — only the session host gets the ZAK.
