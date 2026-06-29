# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# CLAUDE.md — nodeLive (root)

Production educational LMS whose differentiator is a **live meeting experience**:
the Zoom Meeting SDK (Component View) embedded alongside 11 real-time classroom
tools, plus a compliance-grade attendance + recording/watch-tracking backbone.

Two apps. **Read the nested CLAUDE.md for the code you're touching:**
- **`backend/CLAUDE.md`** — FastAPI, SQLAlchemy/Alembic, Celery, webhooks, R2, tests.
- **`frontend/CLAUDE.md`** — React/Vite/Tailwind, Zustand/TanStack, Zoom SDK, player.

Architecture rationale: `plan.md`. Milestones/runbooks: `docs/`.

## Stack (summary)
React 19 + TS + Vite 8, Tailwind 4 + shadcn · Zustand + TanStack Query +
socket.io · Zoom Meeting SDK v6.1 · Python 3.12 + FastAPI + python-socketio ·
Postgres 16 + SQLAlchemy 2.0 (async) + Alembic · Celery + Redis · HS256 JWT in
HttpOnly cookie (Argon2id) · Anthropic Claude (`claude-sonnet-4-6`).

## Commands

Start local infrastructure first (required for both backend tests and dev):
```bash
docker compose up -d postgres redis
```

**Backend** (from `backend/`):
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                        # fill in Zoom + Anthropic + R2 creds
alembic upgrade head
python -m app.scripts.seed                                  # seed demo data (idempotent)
uvicorn app.main:socket_app --reload --port 8000            # socket_app, NOT app
ruff check . && ruff format --check .                       # lint gate (CI)
pytest                                                      # full suite
pytest tests/test_auth.py -k test_login                    # single test / filter
```

**Frontend** (from `frontend/`):
```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # tsc -b && vite build — this is also the typecheck gate (CI)
```

## Core architecture: the three-layer attendance truth model
Compliance comes from three sources at deliberately different trust levels:
1. **SDK events** (frontend) → live counter, UI-only, never persisted.
2. **Webhooks** (`backend/app/api/webhooks.py`) → durable live log.
3. **Reports API** (Celery reconcile) → authoritative post-meeting record.

The whole pipeline is gated on a session reaching `ENDED` (a `LIVE` session is
never reconciled, never appears in the Attendance tab). Status flips three ways:
Zoom `meeting.ended` webhook, the admin "End Session" button, or the hourly
janitor that auto-ends stale `LIVE` sessions. On **free Zoom plans** the Reports
API is paid-only, so reconcile degrades through a fallback chain — Reports →
`past_meetings` → the webhook participant log — feeding the *same* interval-union
math. Detail in `backend/CLAUDE.md`.

Watch-tracking mirrors this (player reports actually-played spans; backend unions
them). The shared primitive is `backend/app/utils/intervals.py` — credit = the
**union of real time intervals**, so reconnects can't double-count and seek-to-end
can't fake completion. Used by BOTH attendance and watch-tracking — never
duplicate it.

## Cross-cutting concerns

**Identity bridge:** `customerKey = user.id[:35]` is set at SDK join time, flows
through Zoom webhooks as `participant.customer_key`, and surfaces in the Reports
API — this is how attendance attributes to a real user. Email is the fallback
match key (customer_key absent for guests). This link is in both the backend
auth dependency and `useZoomSDK.ts`.

**LLM provider:** `backend/app/utils/llm.py` is Anthropic-primary with automatic
Groq fallback (OpenAI SSE protocol over httpx, no SDK). Falls back when
`ANTHROPIC_API_KEY` is unset or an Anthropic call fails before emitting output.
AI features return 501 only when neither key is configured.

**Real-time state split:** live class state (polls, quiz, cue cards, notices,
leaderboard) lives in Zustand (`liveClassStore`) fed by socket events. Everything
else (sessions, recordings, admin data) is TanStack Query. Don't mix them.

## Global gotchas
- **Serve `app.main:socket_app`, not `app`** — or WebSockets 404.
- **COOP/COEP headers are required for the Zoom SDK** — `vite.config.ts` in dev,
  the backend `cross_origin_isolation` middleware in the bundled deploy.
- **Webhook HMAC must be verified over raw bytes** — parsing JSON first changes
  the bytes and silently breaks signature verification.
- **Shell env doesn't persist between commands** — always prefix with
  `source .venv/bin/activate &&` when running backend commands one-off.

## Conventions
- Conventional Commits (`feat:`/`fix:`/`chore:`/`docs:`); signed, under each dev's
  identity; no co-author trailers. The repo owner runs git. Never commit secrets.
- Production-grade only: real passing tests, no stubs/hardcoding to make checks
  green, edge cases handled, verified end-to-end.

## Working here (agents)
- `cd backend/` or `cd frontend/` before launching so search scope + the relevant
  nested CLAUDE.md load (parent CLAUDE.md still applies).
- Long session? Update `SESSION_HANDOFF.md` and resume from it in a fresh session
  instead of relying on auto-compaction.
- Pull large per-domain detail from `docs/` on demand (e.g. `@docs/runbooks/...`)
  rather than loading it every prompt.
