# Deploy (staging)

One Docker image serves the **SPA + API + WebSocket** on a single origin (so auth
cookies, CORS, and the Zoom COOP/COEP headers all just work). The Celery worker
rides in the same container. Postgres + Redis are managed add-ons.

> The same `Dockerfile` runs anywhere — to scale up later (AWS ECS per
> `plan.md §11`), reuse it; only the orchestration config changes.

---

## Render (recommended — free, no credit card)

Everything is declared in **`render.yaml`** (a Blueprint): one free web service +
free Postgres + free Key Value (Redis). No standalone worker (not on Render's free
tier) — it runs inside the web container.

### 1. Get the deploy files onto GitHub
`render.yaml` + `Dockerfile` must be on a branch Render can read. Commit & push
the deploy files (see "What to commit" below), e.g. to `main` or a `deploy` branch.

### 2. Create the Blueprint
- Render dashboard → **New → Blueprint** → connect this GitHub repo → pick the branch.
- Render reads `render.yaml` and provisions the **web service + Postgres + Key Value**.
- `DATABASE_URL`, `REDIS_URL`, and `AUTH_SECRET` are wired automatically.
- Click **Apply**. First build takes a few minutes (frontend build + image).

> `DATABASE_URL` arrives as `postgres://…`; the app auto-coerces it to
> `postgresql+asyncpg://…` (`config._force_asyncpg`), so nothing to edit.

### 3. Optional secrets (dashboard → the web service → Environment)
- `ANTHROPIC_API_KEY` → real AI chat (otherwise the Chat tab shows a graceful toast)
- `ZOOM_SDK_KEY` / `ZOOM_SDK_SECRET` → real Zoom video (+ whitelist the Render URL in your Zoom app)

### 4. Seed the demo data (once)
Web service → **Shell** tab:
```bash
python -m scripts.seed
```
Creates the instructor + 2 students + a **LIVE** session. Logins (password
`password123`): `instructor@nodelive.dev`, `student1@nodelive.dev`, `student2@nodelive.dev`.

### 5. Open + test cross-device
Use the service URL (`https://nodelive-XXXX.onrender.com`). Log in on two devices →
open **"Live Now — Databases Demo"** → Join → drive polls/quiz/cue cards from one,
watch them sync on the other.

### Free-tier notes
- The web service **sleeps after ~15 min idle** → first request cold-starts (~30–60s),
  and the in-container worker sleeps with it. Sockets auto-reconnect + re-hydrate
  via `/live/state`. Fine for testing; upgrade the web plan for an always-on link.
- Free Postgres expires after ~30 days — re-provision when it does.
- 512 MB RAM runs uvicorn + Celery together; light for a demo, bump the plan if tight.

---

## What to commit (deploy artifacts)
These are **infrastructure** (the MP milestone), independent of the feature PRs:
```
Dockerfile  .dockerignore  render.yaml  fly.toml  DEPLOY.md
backend/app/main.py            # serves the SPA + COOP/COEP
backend/app/core/config.py     # FRONTEND_DIST + postgres:// coercion
frontend/src/lib/api.ts        # same-origin in prod
frontend/src/lib/socket.ts     # same-origin in prod
```
Put them on their own branch / PR (e.g. `chore/deploy`) so they don't muddy the
M6 PR.

---

## Alternative — Fly.io (requires a card)
Fly now requires a payment method even within its free allowance. If you add one,
`fly.toml` is ready (separate `web` + `worker` processes). Steps: `fly auth login`
→ set a unique `app` name → `fly apps create` → `fly postgres create/attach` →
`fly redis create` (set `REDIS_URL`) → `fly secrets set AUTH_SECRET=… COOKIE_SECURE=true`
→ `fly deploy` → `fly ssh console -C "python -m scripts.seed"`.
