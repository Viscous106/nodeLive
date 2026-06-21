# CLAUDE.md — linkHQ (root)

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

## Core architecture: the three-layer attendance truth model
Compliance comes from three sources at deliberately different trust levels:
1. **SDK events** (frontend) → live counter, UI-only, never persisted.
2. **Webhooks** (`backend/app/api/webhooks.py`) → durable live log.
3. **Reports API** (Celery reconcile) → authoritative post-meeting record.

Watch-tracking mirrors this (player reports actually-played spans; backend unions
them). The shared primitive is `backend/app/utils/intervals.py` — credit = the
**union of real time intervals**, so reconnects can't double-count and seek-to-end
can't fake completion. Used by BOTH attendance and watch-tracking — never
duplicate it.

## Commands
```bash
docker compose up -d postgres redis     # local infra (needed for tests + dev)
```
Per-app commands live in the nested CLAUDE.md. The two CI gates:
`ruff check . && pytest` (backend) · `npm run build` (frontend — also the typecheck).

## Global gotchas
- **Serve `app.main:socket_app`, not `app`** — or WebSockets 404.
- **COOP/COEP headers are required for the Zoom SDK** — `vite.config.ts` in dev,
  the backend `cross_origin_isolation` middleware in the bundled deploy.

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
