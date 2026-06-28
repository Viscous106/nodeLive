# [nodeLive](https://nodelive-luar.onrender.com/dashboard)

Production-grade educational live-meeting LMS with Zoom Meeting SDK integration. Built for Scaler School of Technology.

## What it is

An LMS dashboard (Scaler-inspired design) where the core feature is a **live meeting experience** — Zoom Meeting SDK embedded in a split-pane layout alongside 11 real-time classroom tools:

- **Cue Cards** — instructor pushes slide-by-slide talking points to all students
- **Live Quiz** — server-timed quiz with speed-scoring and real-time leaderboard
- **Live Polls** — instant vote + live result bar charts
- **AI Chat** — Claude-powered doubt solver with live transcript context
- **Live Bookmarks** — timestamp markers during class, clickable in recording later
- **Leaderboard** — real-time ranking by quiz + poll performance
- **Notice Board** — instructor pushes announcements (critical = full-screen takeover)
- **Pinned Message** — persistent banner in chat panel
- **Raise Hand** — student queue visible to instructor with "call on" action
- **Assignment Unlocking** — instructor unlocks LMS assignments live, students notified instantly
- **Lecture Notes** — upload during/after class; AI-generated notes from transcript post-meeting

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + TypeScript + Vite 8 |
| Styling | Tailwind CSS 4.x + shadcn/ui + Radix UI |
| State | Zustand + TanStack Query |
| Real-time | Socket.io client |
| Meeting SDK | Zoom Meeting SDK v6.1 (Component View) |
| Backend | Python 3.12 + FastAPI |
| WebSocket | python-socketio (ASGI) |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Jobs | Celery + Redis |
| Auth | python-jose (HS256 JWT) + passlib (Argon2id) |
| AI | Anthropic Claude (claude-sonnet-4-6) |
| Storage | Cloudflare R2 (S3-compatible) |

## Repository Structure

```
nodeLive/
├── docs/
│   ├── TEAM.md               — Branch strategy, team assignments, shared setup guide
│   ├── design-tokens.md      — Full Tailwind config, colors, typography, spacing
│   ├── branch-A-dashboard.md — Dev A: day-by-day plan for dashboard + auth
│   └── branch-B-live-meeting.md — Dev B: day-by-day plan for Zoom SDK + live features
├── plan.md                   — Full production architecture (2000+ lines)
├── testing/                  — Zoom SDK MVP prototype (reference implementation)
│   ├── server.js             — Express server with JWT + webhooks
│   ├── src/App.tsx           — Zoom Component View integration reference
│   └── lib/                  — intervals.js, zoomAuth.js (port to Python)
├── frontend/                 — React 19 + Vite app (skeleton on main)
└── backend/                  — Python 3.12 + FastAPI app (skeleton on main)
```

## Branch Strategy

```
main   ← foundation skeleton (FastAPI + Vite + Docker + design system) lives here
  ├── feat/dashboard      ← Dev A: Auth, dashboard, session pages
  └── feat/live-meeting   ← Dev B: Zoom SDK, 11 live-meeting features, WebSocket
```

Both feature branches are cut from `main` and PR back into `main`. There is no
long-lived shared branch — the Day-1 skeleton was merged to `main` directly.

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
cp .env.example .env       # defaults work locally; fill Zoom + Anthropic creds for real meetings/AI
alembic upgrade head       # creates all tables (incl. live-meeting)
python -m scripts.seed     # 1 instructor + 2 students + 5 sessions — login password: password123

# Serve app.main:socket_app (the ASGI wrapper), NOT app — or WebSockets 404.
uvicorn app.main:socket_app --reload --port 8000
```

> The live-meeting backend (Zoom JWT, intervals, socket.io, `/live/state`) runs
> **without real Zoom/Anthropic credentials** — the SDK signature is signed
> locally. Real creds are only needed to actually join a Zoom meeting (frontend)
> or call Claude.

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

## Prototype Reference

The `testing/` directory contains the working Zoom SDK prototype. Key files to port:
- `testing/lib/intervals.js` → `backend/app/utils/intervals.py`
- `testing/lib/zoomAuth.js` → `backend/app/utils/zoom_auth.py`
- `testing/routes/webhooks.js` → `backend/app/api/webhooks.py`
- `testing/src/App.tsx` → `frontend/src/hooks/useZoomSDK.ts`

The prototype fixes 3 bugs present in the official Zoom React sample and uses SDK v6.1 + React 19. See `docs/branch-B-live-meeting.md` §Zoom SDK Notes for all critical patterns.

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
