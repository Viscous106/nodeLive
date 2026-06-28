# Team & Branch Strategy — nodeLive

**Repo:** https://github.com/Viscous106/nodeLive  
**Team size:** 2  
**Stack:** React 19 + TSX + Vite (frontend) | Python 3.12 + FastAPI (backend)  
**Design reference:** Scaler Academy LMS (`/home/laterabhi/Projects/lms-ui-research/`)  
**Master plan:** `plan.md`  
**Design tokens:** `docs/design-tokens.md`

---

## Branch Map

```
main
  ├── feat/dashboard       ← Dev A owns this (Days 1–3)
  └── feat/live-meeting    ← Dev B owns this (Days 1–4)
```

Both branches are off `main` and PR directly back into `main` when ready.

---

## Dev A — Dashboard Branch (`feat/dashboard`)

**What you own:**
- Frontend: Dashboard page, Session Detail page, Auth pages (login/signup)
- Backend: Auth routes (FastAPI), Course/Session CRUD routes, DB migrations (Alembic)
- Design system: TopNav, SideDrawer, Right sidebar, all dashboard widgets

**Branch from:** `main`  
**Branch name:** `feat/dashboard`  
**Detail plan:** `docs/branch-A-dashboard.md`

---

## Dev B — Live Meeting Branch (`feat/live-meeting`)

**What you own:**
- Frontend: `LiveMeetingPage.tsx`, `ZoomPanel.tsx`, all 11 feature panels (quiz, poll, cue cards, etc.)
- Backend: Live class API routes, WebSocket (python-socketio) handlers, Zoom SDK JWT generation
- Workers: Celery tasks (AI summary, caption buffer, quiz timers)

**Branch from:** `main`  
**Branch name:** `feat/live-meeting`  
**Detail plan:** `docs/branch-B-live-meeting.md`

---

## Day 1 Setup (Both devs together, ~4 hrs)

Do this on your own branches simultaneously — no separate shared branch needed.

### Frontend setup
```bash
# /frontend — new Vite + React + TS app
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install tailwindcss @tailwindcss/vite
npx shadcn@latest init
npm install lucide-react zustand @tanstack/react-query socket.io-client react-router-dom
npm install -D @types/node
```

Shared files to create (both devs create these identically, merge conflicts resolved by reviewer):
- `frontend/src/lib/utils.ts` — cn() helper
- `frontend/src/styles/globals.css` — CSS variables (from design-tokens.md)
- `tailwind.config.ts` — full config (from design-tokens.md)
- `frontend/src/types/index.ts` — shared TypeScript interfaces
- `frontend/src/lib/api.ts` — fetch wrapper pointing to FastAPI backend
- `frontend/src/lib/socket.ts` — Socket.io singleton

### Backend setup
```bash
# /backend
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic \
  python-socketio python-jose[cryptography] passlib[argon2] python-multipart \
  celery redis anthropic structlog slowapi sentry-sdk pydantic-settings \
  aiofiles boto3 httpx pytest pytest-asyncio ruff
```

Shared backend files to create:
- `backend/app/main.py` — FastAPI app + CORS + socket mount
- `backend/app/core/config.py` — Pydantic Settings (reads .env)
- `backend/app/db/session.py` — AsyncEngine + get_db dependency
- `backend/app/models/base.py` — Base, metadata
- `backend/alembic/` — init + first migration (all tables from plan.md)
- `backend/app/workers/celery_app.py` — Celery config

### Infrastructure (free tier)
```
PostgreSQL → Neon.tech (free, serverless PostgreSQL — zero ops)
Redis      → Upstash (free, serverless Redis — 10k cmds/day)
Storage    → Cloudflare R2 (free: 10GB storage, 10M reads/month)
Deploy FE  → Vercel (free forever)
Deploy BE  → Railway.app (free $5/month credit) or Render.com
Monitoring → Sentry (free developer plan, 5k errors/month)
```

### Docker Compose (local dev)
```yaml
# docker-compose.yml at repo root
services:
  postgres:
    image: postgres:16-alpine
    environment: { POSTGRES_DB: edustream, POSTGRES_USER: dev, POSTGRES_PASSWORD: dev }
    ports: ["5432:5432"]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

### Environment files
```
backend/.env.example   → DATABASE_URL, REDIS_URL, AUTH_SECRET, ZOOM_SDK_KEY, etc.
frontend/.env.example  → VITE_API_URL, VITE_SOCKET_URL
```

---

## Merge Strategy

1. Both devs PR into `main` when a feature is ready
2. PR must pass: `pytest` (backend) + `tsc --noEmit` (frontend) + `ruff check` (backend)
3. Other dev reviews and approves before merge
4. No direct pushes to `main` — always via PR
5. **Dev A merges first** — Dev B pulls from main after auth is merged to avoid conflicts on shared files

## What NOT to build (out of scope for initial sprint)

- Code editor / assignment grading system (Monaco Editor complexity)
- Referral coins system
- Email notifications
- Mobile responsive layout (build desktop-first)
- Admin panel
- Advanced analytics dashboards
- Recording download/storage (add in Sprint 2)
