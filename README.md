# nodeLive

**A live-class LMS where the class itself is the product.** A Zoom meeting is
embedded next to real-time classroom tools (cue cards, timed quizzes, polls,
raise-hand), and attendance and recording watch-time are
tracked accurately enough to be trusted.

**Live:** <https://nodelive-twbw.onrender.com> · demo logins (password `password123`):
`instructor@nodelive.dev` (instructor/admin), `student1@nodelive.dev`, `student2@nodelive.dev`

> Render free tier: the first request after idle takes 30–60 s while the service
> wakes. If the page is blank, wait and refresh.

> **Team project** by **Yash Virulkar** ([@Viscous106](https://github.com/Viscous106))
> and **Abhinav Singh** ([@OfficialAbhinavSingh](https://github.com/OfficialAbhinavSingh)),
> submitted as our End-Term Software Project with the instructor's approval.
> Who built what is under [Team and contributions](#team-and-contributions).

## Problem statement

Online classes run on a video call plus a pile of disconnected tools: a separate
quiz site, a poll bot, a chat that scrolls past every question, a spreadsheet for
attendance. Students drift because nothing in the call asks anything of them.
Instructors cannot tell who actually attended: a student who reconnects five
times looks present five times, and one who joins and leaves looks present all
class. Recordings are no better, because "watched" usually means "pressed play"
or "dragged the slider to the end".

## Target users

- **Instructors** who teach live online and want interaction (quizzes, polls,
  cue cards, announcements) inside the class instead of in other tabs.
- **Students** who need one place for live classes, recordings, assignments and
  their own progress.
- **Admins** who manage members, roles, courses and schedules and need attendance
  numbers they can defend.

## Solution

nodeLive embeds the Zoom Meeting SDK in a split-pane class view and drives every
classroom tool over Socket.IO, so everyone sees the same state at the same moment,
and a student who reconnects gets the current state back. Attendance and watch
time share one primitive, **the union of real time intervals**, so reconnects
cannot double-count and skipping to the end cannot fake completion.

### Main workflows

| # | Workflow | What happens |
|---|---|---|
| 1 | **Sign up, sign in, roles** | Email + password (Argon2id, JWT in an HttpOnly cookie). Admins invite members and change roles (student / instructor / admin), with a guard against removing the last admin. |
| 2 | **Schedule and start a class** | An admin or instructor creates a course and a session and picks a host. When the host clicks **Join**, a real Zoom meeting is created through Zoom Server-to-Server OAuth and the session goes **LIVE**. Students see "Waiting for the host…" and enter automatically. |
| 3 | **Run the live class** | The host pushes cue cards, runs a server-timed quiz with speed-scored leaderboard, opens polls with live bars, posts notices (critical ones take over the screen), pins messages, calls on raised hands, and unlocks assignments. Leaving and rejoining restores the full state. |
| 4 | **Attendance after class** | When the session ends (Zoom webhook, admin "End session", or an hourly janitor), a Celery job reconciles attendance from Zoom's Reports API, falling back to `past_meetings` and then the webhook participant log on free Zoom plans. It appears in the admin Attendance tab. |
| 5 | **Recordings, assignments, progress** | Zoom recordings are ingested to Cloudflare R2 and played back with watch-% tracking. Students upload assignment files, instructors grade them (email notification), and each student has a progress page with grades and watch %. |

### Error handling and reliability

- Every route validates input with Pydantic v2. Unauthorised and foreign-resource
  requests are refused, and socket rooms check enrolment before a user can join.
- Zoom webhooks are verified with HMAC-SHA256 over the raw body.
- Reconcile tasks retry five times with backoff. Sockets reconnect and rehydrate
  from `GET /sessions/{id}/live/state`.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + TypeScript + Vite 8, Tailwind CSS 4 + shadcn/ui + Radix UI |
| State | Zustand (live class state) + TanStack Query (everything else) |
| Real-time | Socket.IO (python-socketio on the server) |
| Meeting | Zoom Meeting SDK v6.1 (Component View), Zoom S2S OAuth, Zoom webhooks |
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 (async) + Alembic migrations |
| Jobs | Celery + Redis (worker + beat) |
| Auth | HS256 JWT in an HttpOnly cookie, Argon2id password hashing |
| Storage | Cloudflare R2 (S3-compatible) |
| Email | SMTP (no-op when unconfigured) |
| Deploy | One Docker image (SPA + API + WebSocket + worker), Render Blueprint |

## Architecture

```
Browser (React SPA + Zoom SDK)
   │  REST (TanStack Query)        Socket.IO (live class)
   ▼                               ▼
FastAPI  ──────────────────  python-socketio  (served together as app.main:socket_app)
   │  api/: auth, courses, sessions, live, assignments, recordings,
   │        admin, analytics, leaderboard, notes, webhooks
   │  realtime/: rooms (enrolment-checked), emit, captions
   ├── PostgreSQL ── users, courses, sessions, meetings, attendance, recordings, watch_progress …
   ├── Redis ─────── Celery broker + Zoom token cache
   └── Celery ────── attendance reconcile · recording ingest → R2 · session janitor · quiz timers
External: Zoom (SDK join signature, S2S meeting creation, webhooks, Reports API),
          Cloudflare R2, SMTP
```

**Attendance uses three sources at different trust levels.** SDK events drive the
live counter (UI only, never stored). Webhooks give a durable live log. The
Reports API gives the authoritative post-meeting record. All three feed the same
interval-union function, `backend/app/utils/intervals.py`, which watch tracking
also uses.

The full design rationale is in [`plan.md`](plan.md); milestone runbooks are in [`docs/`](docs/).

## Environment variables

Defaults in `backend/app/core/config.py` work for local development. Never commit
real values: use `backend/.env` locally (gitignored) and the Render dashboard in
production.

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | Postgres URL (`postgres://` is coerced to `postgresql+asyncpg://`) |
| `REDIS_URL` | yes | Celery broker and token cache |
| `AUTH_SECRET` | yes (prod) | JWT signing key; `render.yaml` generates it |
| `COOKIE_SECURE` | prod | `true` over HTTPS |
| `CORS_ORIGIN` | dev | Frontend origin in development (production is same-origin) |
| `BOOTSTRAP_ADMIN_EMAILS` | no | Emails granted admin on sign-up or login |
| `ZOOM_SDK_KEY`, `ZOOM_SDK_SECRET` | for video | Meeting SDK credentials (join signatures) |
| `ZOOM_S2S_ACCOUNT_ID`, `ZOOM_S2S_CLIENT_ID`, `ZOOM_S2S_CLIENT_SECRET`, `ZOOM_HOST_EMAIL` | to start classes in-app | Create meetings and fetch the host ZAK |
| `ZOOM_WEBHOOK_SECRET_TOKEN` | for attendance | Verifies Zoom webhooks |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_ENDPOINT_URL` | for recordings | Recording storage |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | no | Email notifications |
| `RUN_WORKER` | no | `0` disables the in-container Celery worker |

## Deployment

Deployed on Render from [`render.yaml`](render.yaml): one free web service built
from the `Dockerfile`, plus free Postgres and free Key Value (Redis). On boot,
`backend/start.sh` runs `alembic upgrade head`, seeds the demo data in the
background, starts Celery beat and worker, then serves `app.main:socket_app`.
Step-by-step instructions are in [`DEPLOY.md`](DEPLOY.md).

Free-tier caveats: the service sleeps after ~15 min idle, and Render's free
Postgres expires after ~30 days and must be re-provisioned.

## Local Development

### 1. Infrastructure

```bash
docker compose up -d postgres redis
```

### 2. Backend (run from `backend/`)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install uv && uv pip install -r requirements.txt
cp .env.example .env       # defaults work locally; fill Zoom creds for real meetings
alembic upgrade head       # creates all tables (incl. live-meeting)
python -m scripts.seed     # 1 instructor + 2 students + 5 sessions — login password: password123

# Serve app.main:socket_app (the ASGI wrapper), NOT app — or WebSockets 404.
uvicorn app.main:socket_app --reload --port 8000
```

> The live-meeting backend (Zoom JWT, intervals, socket.io, `/live/state`) runs
> **without real Zoom credentials** — the SDK signature is signed
> locally. Real creds are only needed to actually join a Zoom meeting (frontend).

### 3. Frontend (run from `frontend/`)

```bash
cd frontend
npm install
npm run dev                # http://localhost:5173
```

### 4. Workers (optional — only needed for Celery features)

```bash
cd backend && source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```

### Verify it's running

```bash
# Health
curl localhost:8000/health         # liveness, no deps
curl localhost:8000/health/ready   # readiness, pings the DB
open http://localhost:8000/docs    # Swagger UI

# Log in (saves the HttpOnly session cookie), then hit the live routes
curl -c cj.txt -X POST localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"instructor@nodelive.dev","password":"password123"}'
curl -b cj.txt localhost:8000/api/sessions                       # list sessions → grab an id
curl -b cj.txt -X POST localhost:8000/api/sessions/<ID>/join     # → { signature, sdkKey, zoomMeetingId }
curl -b cj.txt localhost:8000/api/sessions/<ID>/live/state       # reconnect snapshot
```

### Quality gates (CI)

```bash
# Backend (needs postgres up — conftest auto-creates the nodelive_test DB)
cd backend && source .venv/bin/activate
ruff check . && ruff format --check .   # lint
pytest                                  # tests

# Frontend
cd frontend
npm run build                           # tsc -b && vite build (also the typecheck gate)
```

## Design Reference

UI reference in `/lms-ui-research/` (separate folder). Design system:
- **Font:** Source Sans Pro (Google Fonts)
- **Primary:** `#2563EB`
- **Page background:** `#EFF6FF`
- **Components:** shadcn/ui with Tailwind design tokens (see `docs/design-tokens.md`)

## Security

- Zoom webhook HMAC-SHA256 verified over raw body
- JWT tokens in HttpOnly cookies (`sameSite: strict`)
- Argon2id password hashing
- Pydantic v2 input validation on every route
- COOP/COEP headers required for Zoom SDK (already in Vite config)

## Team and contributions

| | Main areas (from the commit history) |
|---|---|
| **Yash Virulkar** ([@Viscous106](https://github.com/Viscous106)) | The live-meeting experience end to end: live feature APIs and socket events (M3), the live class page (M4), Zoom webhooks and attendance reconcile (M6), recordings with R2 ingest and watch tracking (M7), Zoom S2S auto-created meetings with host ZAK and the waiting-for-host flow, admin Members/Roles and Sessions/Courses, deployment (Docker, Render), and integrating the dashboard branches |
| **Abhinav Singh** ([@OfficialAbhinavSingh](https://github.com/OfficialAbhinavSingh)) | Dashboard, auth and session pages; admin Overview and Attendance tabs; the attendance pipeline repair and free-Zoom-plan fallbacks; socket-presence attendance; student progress page; profile settings; assignment file upload; dark mode; mobile responsiveness; email notifications |

Both of us wrote backend tests (`backend/tests/`, 40+ files) for our areas.
