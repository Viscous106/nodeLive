# Milestones — Dev B · Live Meeting, Realtime, AI & Compliance (`feat/live-meeting`)

Owner: **Viscous106**
Detail plan: [`docs/branch-B-live-meeting.md`](docs/branch-B-live-meeting.md) · Master plan: [`plan.md`](plan.md) (§17 roadmap)

End-to-end production scope, not just the MVP sprint. Each milestone = one PR into
`main` (small, reviewed, green CI, **squashed to one signed commit** at merge).
A milestone is **Done** only when its Definition of Done holds and the PR is merged.

### Ownership split (full project)
Dev B owns the **live + intelligence + compliance backend**: Zoom SDK integration,
python-socketio realtime, the 11 live features, the AI pipeline (live + post-meeting),
and the compliance backbone (webhooks → attendance reconcile → recording ingest →
watch-tracking union). Dev A owns auth/accounts, dashboard, LMS content, analytics
UI, admin. Shared seams are called out per milestone.

> **Dependency:** the auth + session contract (`User`, `ClassSession`,
> `get_current_user`, `GET/PATCH /api/sessions/:id`) ships on `main` via Dev A's
> PR #2. Pull `main` once it merges. **M1 has no dependency — start now.**

### Roadmap mapping
| Milestone | plan.md phase | Status |
|---|---|---|
| M1 Zoom JWT + intervals | Phase 0/1 | ✅ done (PR #10) |
| M2 Realtime backbone | Phase 1 | ✅ done (PR #11) |
| M3 Live feature APIs | Phase 1/2 | ✅ done (PR #12) |
| M4 Frontend live page | Phase 1/2 | ✅ done (PR #13) |
| M5 Live AI chat + polish | Phase 4 (live) | |
| M6 Webhooks + attendance reconcile | compliance (Phase 3/5) | |
| M7 Recording ingest + watch-tracking | compliance (Phase 3) | |
| M8 Post-meeting AI pipeline | Phase 4 | |
| M9 AI recommendations + engagement analytics | Phase 4 | |
| MP Production hardening (shared) | Phase 5 | |

---

## M1 — Zoom JWT + intervals (no dependencies — start now) · _Phase 0/1_

- [x] `app/utils/zoom_jwt.py` — HS256 SDK signature (port from `testing/server.js`) + tests
- [x] `app/utils/intervals.py` — `merge_intervals` / `coverage_fraction` (port from `testing/lib/intervals.js`) + tests
- [x] `POST /api/sessions/:id/join` → `{ signature, sdkKey, zoomMeetingId }` (uses merged auth + ClassSession)

**DoD:** join returns a valid SDK signature; intervals tests encode **"seek-to-end yields 15%, not 100%"**; ruff + pytest green.

## M2 — Realtime backbone · _Phase 1_

- [x] python-socketio mounted via `app.main:socket_app`; connect handler validates JWT cookie
- [x] `join_session` → room join (`session:{id}`, instructor + private rooms)
- [x] `caption_received` → Redis sorted-set buffer (last 50)
- [x] `app/models/live_meeting.py` (CueCard, Poll, Quiz, Bookmark, Notice, PinnedMessage, LeaderboardPoint) + migration 002
- [x] `GET /api/sessions/:id/live/state` — full snapshot for reconnects

**DoD:** a client connects with a real session cookie, joins its room, and `/live/state` returns the current snapshot.

## M3 — Live feature APIs + socket events · _Phase 1/2_

- [x] Cue cards (`cuecard:shown`), Polls (`poll:launched|results|closed`)
- [x] Quiz: create + launch + **Celery** question timer + scoring (`quiz:*`, `leaderboard:update`)
- [x] Notices, Pinned message, Raise hand (ephemeral), Bookmarks, Assignment unlock · **seam:** `assignment:unlocked` consumed by Dev A's assignments

**DoD:** ✅ every event round-trips to the right room; quiz scoring + poll percentages have pytest coverage; handlers idempotent.

_Notes:_ leaderboard points are awarded only on the **first** response insert
(poll re-vote / quiz re-answer / reconnect can't double-count); quiz timing is
server-authoritative (`quizzes.launched_at` + position × `time_limit_secs`), so a
late answer scores 0; the timed rotation is scheduled all-at-launch as Celery
`quiz.emit_event` tasks (no correct answer ever leaves the server). **Follow-up
for M4:** `/live/state` doesn't yet carry the in-flight question + remaining time,
so a mid-quiz reconnect waits for the next rotation — surface this in the live page.

## M4 — Frontend live-meeting page · _Phase 1/2_

- [x] `LiveMeetingPage` split-pane; `ZoomPanel` + `useZoomSDK` (ported from `testing/src/App.tsx` with the Appendix-D fixes: `patchJsMedia`, `leaveOnPageUnload`, `sdkKey`, `customerKey`)
- [x] `FeaturePanel` tabs + panels (Chat, Quiz, Poll, Leaderboard, Bookmarks, Notes)
- [x] `CueCardOverlay`, `NoticeOverlay`, `RaiseHandQueue`
- [x] `useSocket`/`useSocketEvents`/`useLiveState` + `liveClassStore` (Zustand)

**DoD:** ✅ `/live/:sessionId` route renders the split pane; SDK joins with `customerKey = user.id.slice(0,35)`; COOP/COEP already in `vite.config.ts`; `npm run build` (tsc + vite) green.

_Verified locally:_ full typecheck/build passes; all live modules transform in Vite; app boots; **integration round-trip passes** — a `socketio.AsyncClient` with the session cookie + browser `Origin` connects (cookie auth + CORS), joins the room, and receives `poll:launched` after a REST `POST /polls`. Visual mount of the authed page to be eyeballed by clicking **Join Session** (seed session `seed-session-up-1` set to LIVE locally).

_Deferred (by design):_ **AI chat → M5** (ChatPanel placeholder); leave-confirm uses `window.confirm` (richer dialog → M5); assignment-unlock has no live-page button yet (endpoint shipped in M3; needs an assignment list surfaced here).

_Known issues for the PR:_
- **Carryover:** `/live/state` omits the in-flight quiz question + remaining time, so a mid-quiz reconnect waits for the next rotation — a small backend add (M3 follow-up) closes it.
- **Stale CRITICAL notice on reconnect:** `NoticeOverlay` reads hydrated `recentNotices`, so a past CRITICAL notice in the snapshot re-pops as a full-screen takeover on rejoin until locally dismissed — `/live/state` has no dismissed-state. Fix when notices gain a lifecycle.
- **StrictMode socket churn:** dev double-invokes effects → connect → `disconnectSocket()` → reconnect; ends consistent (one live socket) but worth a glance in the backend log if events ever seem missing.

## M5 — Live AI chat + polish · _Phase 4 (live half)_

- [ ] `POST /api/sessions/:id/live/ai-chat` — streaming Claude over socket (`ai:response-chunk|done`) with transcript context
- [ ] `useAiStream`; toasts (assignment unlock, quiz score, notice); leave-confirm dialog
- [ ] Zoom join-failure error states

**DoD:** AI answers using live transcript context; build + tests green.

## M6 — Zoom webhooks + attendance reconcile · _compliance (Phase 3/5)_

The durable + authoritative layers of the three-layer attendance model.

- [ ] `app/api/webhooks.py` — HMAC-SHA256 over **raw body** (port from `testing/routes/webhooks.js`); handlers for `meeting.started|ended|participant_joined|participant_left` → `attendance_sessions`
- [ ] `jobs`-style queue + Celery reconcile task (runs ~5 min after `meeting.ended`)
- [ ] Reports-API reconcile → `attendance_final` (authoritative tie-breaker), using the **meeting UUID** (not numeric id) + `customer_key || email` identity match
- [ ] Attendance credit = **union of intervals** (reuse `intervals.py`)

**DoD:** webhook signature verified on raw bytes; reconnects don't double-count attendance; `attendance_final` is the source of truth; pytest covers union + identity-match edge cases.

## M7 — Recording ingest + watch-tracking · _compliance (Phase 3)_

- [ ] Recording download (append webhook `download_token` / S2S OAuth) → object storage (R2/S3); Celery ingest job (idempotent)
- [ ] `POST /api/recordings/:id/heartbeat` — accept played spans · **seam:** UI/player owned by Dev A (M6)
- [ ] Watch coverage = **union of watched spans** via `intervals.py`; expose read-model (watch %) for the dashboard
- [ ] CloudFront/CDN signed URLs (return 501 when not configured — by design)

**DoD:** recording lands in storage; seeking to the end yields partial (not 100%) watch credit; watch % read-model consumed by Dev A's dashboard.

## M8 — Post-meeting AI pipeline · _Phase 4_

- [ ] Celery chain after `meeting.ended`: transcript fetch → AI summary → lecture notes → auto-quiz draft
- [ ] `ai_meeting_summaries` table; "summary ready" event · **seam:** triggers Dev A's email + summary page
- [ ] AI-generated quiz → instructor review + one-click publish (reuses M3 quiz)

**DoD:** within ~10 min of a class ending, a summary + notes exist; instructor can publish an AI quiz; prompt-injection guarded.

## M9 — AI recommendations + engagement analytics · _Phase 4_

- [ ] Personalized learning recommendations (per student per course)
- [ ] Weekly engagement analysis (Claude prompt over attendance + quiz/poll data) · **seam:** surfaced by Dev A's analytics dashboards (M7)
- [ ] AI doubt-solver (post-class, over recording transcript)

**DoD:** recommendations + weekly engagement summaries generated on a Celery beat schedule; outputs consumed by Dev A's UI.

## MP — Production hardening (shared with Dev A) · _Phase 5_

Dev B slice:
- [ ] Sentry (backend); nginx WebSocket proxy + COOP/COEP + rate limiting
- [ ] k6 load test: 500 concurrent students, 20 classes, Zoom SDK stress
- [ ] Prometheus metrics for socket/Celery; prompt-injection security tests
- [ ] GitHub Actions production deploy (backend → Railway/Render) with approval gate

**DoD (shared):** production deploy passes the 500-student load test; runbook covers deploy/rollback/restore/incident. See Dev A's MP for the frontend half.

---

### Conventions
- Branch from `main`, PR back to `main`. **Signed commits** under your identity (set up GPG — `main` will require it); no co-author trailers.
- **Commit hygiene:** commit freely on the branch; **squash to logical signed commits before merge** (one per small PR). Don't leave "fix typo" commits on `main`.
- Serve `app.main:socket_app` (not `app`) or WebSockets 404.
- Don't duplicate `intervals` logic — it's the shared compliance primitive used by attendance **and** watch-tracking.
- Any change to a **shared** shape (User/ClassSession/schemas/socket events/read-models) → flag in the PR and tell Dev A.
