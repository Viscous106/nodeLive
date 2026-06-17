# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Zoom Meeting SDK (Component View) app with a **compliance-grade attendance + recording-watch-tracking** backend. The frontend (React + Vite + TS) embeds a Zoom meeting; the Express backend records who attended (and for how long) and how much of the stored recording each user actually watched. "Compliance-grade" means watch/attendance credit is computed from the **union of real time intervals** — so reconnects can't double-count attendance and seeking to the end can't fake watch completion.

The full design rationale lives in `/home/viscous/.claude/plans/i-want-you-to-quizzical-catmull.md`.

## Commands

```bash
npm run dev:all     # frontend (vite, :5173) + backend (express, :4000) together
npm run dev         # frontend only
npm run dev:server  # backend only (node server.js)
npm test            # all backend tests (node --test over lib/ routes/ workers/)
npm run build       # tsc -b && vite build (also the typecheck gate)
npm run lint        # eslint

# run a single test file
node --test routes/recordings.test.js
```

There is no test runner config — tests are plain `node:test` files named `*.test.js` next to the code they cover. The `test` script globs `lib/*.test.js routes/*.test.js workers/*.test.js`; add new test directories to that glob in `package.json`.

## Architecture: the three-layer truth model

Attendance is **not** a single feature. Three sources with different trust levels, deliberately:

1. **SDK events** (`src/App.tsx`, `getAttendeeslist` + `user-added`/`user-removed`) → the live in-meeting counter. **UI only, never persisted** — it dies when the browser tab closes.
2. **Webhooks** (`routes/webhooks.js`) → the durable live log written to `attendance_sessions`. Survives the client closing.
3. **Reports API** (`workers/reconcile.js`) → the authoritative post-meeting record in `attendance_final`. This is the tie-breaker.

Watch tracking is the same shape: the player reports actually-played spans, the backend unions them.

### The shared compliance primitive

`lib/intervals.js` (`mergeIntervals` / `coverageFraction`) is used by **both** `workers/reconcile.js` (union a user's join/leave sessions) and `routes/recordings.js` (union watched spans). It is the single most important piece of logic — its test `lib/intervals.test.js` encodes the rule "seek-to-end yields 15%, not 100%". Don't duplicate this logic anywhere.

### Identity glue

`customerKey` passed at SDK join time (`src/App.tsx` `deriveCustomerKey`) flows back as `participant.customer_key` in webhooks and (intended) in the Reports API, so attendance attributes to a real app user. **Email is the fallback match key** everywhere because `customer_key` may be absent (guest joins) — see the `customer_key || email` grouping in `reconcileParticipants`.

### Background work

Slow/delayed work (reconcile 5 min after `meeting.ended`, recording download→S3) is **not** done inline. Webhooks insert rows into the `jobs` table; `workers/jobRunner.js` polls it on an interval, claims atomically, dispatches by `type`, and retries with backoff. Handlers must be idempotent.

## Critical gotchas

- **Webhook body ordering**: `routes/webhooks.js` must be mounted with `express.raw()` **before** the global `express.json()` in `server.js` — the HMAC signature is verified over the exact raw bytes. Moving it breaks signature verification silently (every webhook → 401).

- **`lib/db.js` opens the database at import time** from `process.env.DATABASE_URL`. In tests this is a footgun: any **static** `import` of a module that transitively loads `db.js` opens the DB *before* the test can set an isolated `DATABASE_URL` (ESM hoists imports above top-level statements). Test files therefore set `DATABASE_URL` to a temp path and **dynamically `import()`** db-touching modules inside `before()`. Follow that pattern in new tests or they'll pollute `./data/app.sqlite` and fail nondeterministically only when run as a suite.

- **Reports API needs the meeting UUID, not the numeric id** (`encodeMeetingUuid` in `workers/reconcile.js`) — the numeric id returns the wrong instance for recurring meetings. UUIDs containing `/` or `//` are double-URL-encoded.

- **Recording download URLs are 401 without auth** — append the webhook `download_token` (or an S2S OAuth token). See `workers/recordingIngest.js`.

## Known incomplete (intentional)

- **Auth is a stub**: heartbeat/signed-URL routes read identity from an `x-user-id` header (`getUserId` in `routes/recordings.js`, marked `TODO(auth)`). Real session auth (a `users` table exists for it) must replace this before the compliance guarantees actually hold.
- Zoom S2S OAuth, AWS S3, and CloudFront are wired to `.env` (`.env.example`) but untested against live endpoints. CloudFront-not-configured returns 501 by design.
