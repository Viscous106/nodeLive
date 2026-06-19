# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## What this is

**linkHQ** — a production-grade educational LMS whose core feature is a **live
meeting experience**: the Zoom Meeting SDK (Component View) embedded in a
split-pane layout alongside 11 real-time classroom tools (cue cards, server-timed
quiz, live polls, AI chat, bookmarks, leaderboard, notices, pinned message, raise
hand, assignment unlocking, lecture notes). The dashboard shell is Scaler-Academy
inspired.

The production app lives in `backend/` (Python 3.12 + FastAPI) and `frontend/`
(React 19 + Vite + TypeScript). The full architecture rationale is in `plan.md`;
per-developer day-by-day plans are in `docs/`.

> **`testing/` is a reference prototype, not the app.** It is a Node/Express +
> Zoom SDK MVP that proved out the Component-View integration and the
> compliance-grade attendance/watch-tracking logic. Its files are **ported to
> Python**, not run in production. Do not add features there.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React 19 + TypeScript + Vite 8, Tailwind 4 + shadcn/ui |
| State | Zustand + TanStack Query; Socket.io client |
| Meeting SDK | Zoom Meeting SDK v6.1 (Component View) |
| Backend | Python 3.12 + FastAPI; python-socketio (ASGI) for WebSocket |
| DB | PostgreSQL 16 + SQLAlchemy 2.0 (async) + Alembic |
| Jobs | Celery + Redis |
| Auth | python-jose (HS256 JWT in HttpOnly cookie) + passlib (Argon2id) |
| AI | Anthropic Claude (`claude-sonnet-4-6`) |

## Commands

```bash
# Infra (local)
docker compose up -d postgres redis

# Backend (run from backend/)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill Zoom + Anthropic creds
alembic upgrade head
uvicorn app.main:socket_app --reload --port 8000   # NOTE: socket_app, not app

ruff check . && ruff format --check .   # lint gate (CI)
pytest                                   # tests (CI) — needs postgres up;
                                         # conftest auto-creates the linkhq_test DB

# Frontend (run from frontend/)
npm install
npm run dev        # http://localhost:5173
npm run build      # tsc -b && vite build — also the typecheck gate (CI)
```

Backend tests are `pytest` files under `backend/tests/`. Config (ruff + pytest)
is in `backend/pyproject.toml`. CI is `.github/workflows/ci.yml`.

## Architecture: the three-layer attendance truth model

Attendance is **not** one feature — three sources with deliberately different
trust levels (see `plan.md` for the full design; the prototype proved it in
`testing/`):

1. **SDK events** (frontend `useZoomSDK`) → live in-meeting counter. **UI only,
   never persisted** — dies when the tab closes.
2. **Webhooks** (`backend/app/api/webhooks.py`, ported from
   `testing/routes/webhooks.js`) → durable live log. Survives the client closing.
3. **Reports API** (Celery reconcile worker) → authoritative post-meeting record.
   The tie-breaker.

Watch-tracking mirrors this: the player reports actually-played spans; the
backend unions them.

### The shared compliance primitive

`backend/app/utils/intervals.py` (ported from `testing/lib/intervals.js`:
`mergeIntervals` / `coverageFraction`) is the single most important piece of
logic — it computes credit from the **union of real time intervals** so reconnects
can't double-count attendance and seeking to the end can't fake watch completion
(the rule "seek-to-end yields 15%, not 100%"). It is used by **both** attendance
reconcile and watch-tracking. Don't duplicate it; keep its tests.

### Identity glue

`customerKey` passed at SDK join (`user.id.slice(0,35)`) flows back as
`participant.customer_key` in webhooks and the Reports API, so attendance
attributes to a real user. **Email is the fallback match key** because
`customer_key` may be absent (guest joins).

## How the work is split (2 devs)

- **Dev A — `feat/dashboard`** (OfficialAbhinavSingh): auth, User/Course/Session
  models + migrations, dashboard + session-detail pages, shared layout/design system.
- **Dev B — `feat/live-meeting`** (Viscous106): Zoom JWT + SDK panel, python-socketio
  server, the 11 live features, Celery quiz/AI workers, webhooks, intervals port.

Both branch off `main`. The **shared contract** (User/ClassSession Pydantic + TS
shapes, socket event catalog, API routes) is frozen up front so the two sides
build in parallel and meet in the middle. See `docs/TEAM.md`,
`docs/branch-A-dashboard.md`, `docs/branch-B-live-meeting.md`.

## Critical gotchas

- **Serve `app.main:socket_app`, not `app`** — uvicorn must serve the ASGI
  callable that wraps FastAPI + socket.io, or WebSockets 404.
- **Webhook HMAC is over raw bytes** — read the raw request body for the
  SHA-256 signature check; parsing to JSON first breaks verification.
- **Reports API needs the meeting UUID, not the numeric id** — the numeric id
  returns the wrong instance for recurring meetings; UUIDs with `/` are
  double-URL-encoded.
- **Recording download URLs are 401 without auth** — append the webhook
  `download_token` (or an S2S OAuth token).
- **COOP/COEP headers are required for the Zoom SDK** — set in `vite.config.ts`
  (`Cross-Origin-Opener-Policy: same-origin`, `Cross-Origin-Embedder-Policy:
  require-corp`); must be replicated in the production proxy.
- **Importing `app.main` does not open the DB** — asyncpg connects lazily, so
  smoke tests and `from app.main import app` stay cheap. `/health` has no deps;
  `/health/ready` pings the DB.

## Known incomplete (intentional)

- **Auth wiring is being built on `feat/dashboard`.** Until `get_current_user`
  and the User model land, live-meeting routes (Dev B) stub identity. Real cookie
  session auth must land before the compliance guarantees hold.
- Zoom S2S OAuth, Cloudflare R2 (S3-compatible), and recording ingest are wired
  to `.env` (`backend/.env.example`) but untested against live endpoints.

## Conventions

- **Commits are signed and authored under each dev's own identity.** Conventional
  Commits (`feat:`, `fix:`, `chore:`, `docs:`). No co-author trailers.
- **No direct pushes to `main`** — PR + green CI + the other dev's review.
- Keep PRs small and scoped to one feature slice.
- Never commit `.env` or secrets.
