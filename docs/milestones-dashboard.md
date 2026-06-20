# Milestones — Dev A · Dashboard, LMS & Platform (`feat/dashboard`)

Owner: **OfficialAbhinavSingh**
Detail plan: [`docs/branch-A-dashboard.md`](docs/branch-A-dashboard.md) · Master plan: [`plan.md`](plan.md) (§17 roadmap)

End-to-end production scope, not just the MVP sprint. Each milestone = one PR into
`main` (small, reviewed, green CI, **squashed to one signed commit** at merge).
A milestone is **Done** only when its Definition of Done holds and the PR is merged.

### Ownership split (full project)
Dev A owns the **student/instructor-facing platform**: auth & accounts, dashboard,
LMS content (courses, assignments, notes, recordings UI), analytics dashboards,
admin, and the frontend half of production hardening. Dev B owns the live-meeting,
realtime, Zoom, AI pipeline, and the compliance **backend** (webhooks, reconcile,
watch-tracking). Shared seams are called out per milestone.

### Roadmap mapping
| Milestone | plan.md phase | Status |
|---|---|---|
| M0 Auth + session contract | Phase 0 | ✅ done (PR #2) |
| M1 App shell & design system | Phase 0 | ✅ done (PR #3) |
| M2 Dashboard page | Phase 0/3 | ✅ done (PR #4) |
| M3 Session detail | Phase 0/3 | ✅ done (PR #5) |
| M4 Frontend polish & hardening | Phase 1/2 support | ✅ done (PR #7) |
| M5 Assignments & grading | Phase 3 | ✅ done (PR #9) |
| M6 Lecture notes + recording player (+ watch-tracking UI) | Phase 3 + compliance | 🟡 lecture notes ✅ (PR #17); recording player + watch-tracking deferred (needs Dev B M7 recordings) |
| **AF Organizations & Memberships** (foundation) | identity | 📐 designed ([spec](superpowers/specs/2026-06-20-admin-dashboard-design.md)) — prerequisite for AD; **additive** (`User.role` kept as a synced mirror; dropped in a later contract step) |
| **AD Admin Dashboard** (members/roles, sessions, attendance, overview) | Phase 3/4/6 | 📐 designed ([spec](superpowers/specs/2026-06-20-admin-dashboard-design.md)) — **consolidates M7 + M9** |
| ~~M7 Analytics dashboards~~ | Phase 3/4 | → folded into **AD** (Attendance + Overview tabs) |
| M8 Accounts: OAuth, profile, email | Phase 6 | (org/membership identity foundation moves under **AF**) |
| ~~M9 Admin panel + responsive/dark/PWA~~ | Phase 6 | admin panel → **AD**; responsive/dark/PWA stay here |
| MP Production hardening (shared) | Phase 5 | |

---

## M0 — Auth + Session Contract ✅ DONE (PR #2)

- [x] `User`/`UserRole`, Argon2id, HS256 JWT in HttpOnly cookie; signup/login/logout/me; `get_current_user`/`require_role`
- [x] `Course`/`ClassSession`/`SessionStatus`; `GET`/`PATCH /api/sessions/:id`
- [x] Migration 001 (reversible) + `scripts/seed.py`; 16 tests; CI green

**DoD:** ✅ contract frozen; Dev B unblocked.

## M1 — App shell & design system ✅ DONE (PR #3) · _Phase 0_

- [x] Inter (self-hosted, COEP-safe) + Scaler tokens; shadcn-style primitives (Button, Input, Label, Card, Badge, Skeleton, Avatar, Spinner, Dropdown)
- [x] `TopNav`, `SideDrawer` (animated), `DashboardLayout` (content + right-sidebar slot)
- [x] `LoginPage` + `SignupPage` wired to `/api/auth`; `useAuth` (React Query); `uiStore` (Zustand)
- [x] React Router v7 + auth guards (`/` → dashboard if authed else login)

**DoD:** ✅ login → dashboard verified against the live backend; guards bounce anon users; `npm run build` green.

## M2 — Dashboard page · _Phase 0/3_

- [ ] Backend: `GET /api/sessions?status=`, `/api/sessions/this-week`, `/api/courses`, `/api/dashboard/widgets`
- [ ] `TimetableSection` + `DateTabStrip` + `ClassCard`
- [ ] `ContinueWatchingSection` + `VideoCard` (watch-progress bar)
- [ ] `DashboardSidebar`: `PerformanceWidget`, `NoticeBoardWidget`, `YearRevisitedBanner`
- [ ] `useDashboard` hooks; loading skeletons; empty states

**DoD:** dashboard renders seeded data end-to-end; skeletons on every fetch; empty states; pytest covers new endpoints.

## M3 — Session detail page · _Phase 0/3_

- [ ] Backend: `GET /api/sessions/:id/similar`
- [ ] `SessionDetailPage` (`/session/:id`) + breadcrumb
- [ ] `UpcomingSessionHero` ("Join Session" → `/live/:id`) · **seam:** route owned by Dev B
- [ ] `SessionTabBar` (Feedback locked until ENDED), `SimilarSessionsRow`

**DoD:** dashboard → session detail → Join routes to the live URL; tabs gate by status; tests for `/similar`.

## M4 — Frontend polish & hardening · _Phase 1/2 support_

- [ ] Error boundaries per page; full skeleton/empty coverage
- [ ] API client: 401 handling + session refresh; toast system (shared with Dev B)
- [ ] Accessibility pass (focus, labels, keyboard nav on drawer/dropdown)
- [ ] Route-level code splitting; Lighthouse pass on dashboard

**DoD:** clean CI; no console errors; desktop layout matches design ref.

## M5 — Assignments & grading · _Phase 3_

- [ ] Models + migration: `Assignment`, `Submission` (+ status, grade) · **seam:** Dev B emits `assignment:unlocked`
- [ ] `POST/GET/PATCH /api/assignments` (CRUD, instructor-gated via `require_role`)
- [ ] Submission upload → object storage (R2/S3) with presigned URLs
- [ ] Student view: list / submit / view grade; Instructor view: grading interface
- [ ] pytest: authz, submission lifecycle, grade write

**DoD:** assign → submit → grade → view loop works; uploads stored in R2; instructor-only gates enforced.

## M6 — Lecture notes + recording player + watch-tracking UI · _Phase 3 + compliance_

- [ ] `LectureNote` model; upload (PDF/DOCX → R2) + signed download URL
- [ ] Recording player page; **bookmarks render as clickable timestamps** (reads Dev B's `Bookmark`)
- [ ] Watch-tracking client: report played spans → `POST /api/recordings/:id/heartbeat` · **seam:** union/coverage computed by Dev B's backend (`intervals`)
- [ ] Surface watch % + attendance % on dashboard/session (consumes compliance read-models)

**DoD:** play recording, seek, jump to a bookmark; watch % reflects the **union of real played spans** (seek-to-end ≠ 100%); notes download via signed URL.

## AF — Organizations & Memberships (foundation) · _identity_

Design: [`docs/superpowers/specs/2026-06-20-admin-dashboard-design.md`](superpowers/specs/2026-06-20-admin-dashboard-design.md) (Part A). **Prerequisite for AD.**

- [x] `Organization` + `Membership` (user↔org↔role, reuses `UserRole`) + `Invitation` models + reversible migration that inserts the default org and backfills memberships from `users.role` (**keeps `users.role`** as a synced mirror — expand-contract)
- [x] **Additive** `get_current_membership` / `get_default_org` / `require_org_role(*roles)` for the admin surface only; existing guards/`UserOut`/frontend untouched (still read the synced `users.role`)
- [x] One role-write service (`services/roles.py`) updates `membership.role` + the `users.role` mirror together; invite (email-locked link) honored at `POST /api/auth/signup` via `inviteToken`; seed (instructor → org ADMIN) + `set_role` write both · `count_org_admins` ready for the AD last-admin guard · **seam:** new org/membership models flagged to Dev A; the later **contract** step (drop `users.role`) is coordinated

**DoD:** ✅ non-breaking (131 tests green, existing untouched); `require_org_role` gates; invite→signup assigns role (mismatch/expired/revoked rejected); role writes sync membership + mirror; backfill migration round-trips (up→down→up clean, 1:1 backfill verified). Admin endpoints + last-admin demotion guard land in **AD**.

## AD — Admin Dashboard · _Phase 3/4/6 — consolidates M7 + M9_

Design: [`docs/superpowers/specs/2026-06-20-admin-dashboard-design.md`](superpowers/specs/2026-06-20-admin-dashboard-design.md) (Part B). `/admin`, ADMIN-only, built on **AF**. Phased: Members → Sessions → Attendance → Overview.

- [x] **Members & Roles** tab — list members, promote/demote (last-admin guard), invite-by-link, revoke + invite-aware signup · `/api/admin/*` + `/admin` UI (12 backend tests)
- [x] **No-shell bootstrap admin** — `BOOTSTRAP_ADMIN_EMAILS` (default `abhinav.singh@scaler.com`) auto-grants ADMIN on login/signup, so the first admin exists on the deployed instance without Shell access (4 tests)
- [ ] **Sessions** tab — list/create/edit/cancel class sessions (real Zoom auto-create = fast-follow)
- [ ] **Attendance** tab — per-session + per-student from `attendance_final` (empty until real Zoom creds feed M6 reconcile)
- [ ] **Overview** tab — counts, recent activity, engagement snapshot (leaderboard / quiz-poll participation)

**DoD:** an org admin manages roles, schedules sessions, and views attendance + an overview; all `require_org_role(ADMIN)`-gated; empty states where data is unfed.

## M7 — Analytics dashboards · _Phase 3/4_ → **folded into AD**

Superseded by AD (Attendance + Overview tabs). Remaining student-facing pieces:
- [ ] Student "Year Revisited" / progress summary (consumes Dev B's AI engagement analysis when available)

**DoD:** instructor attendance/engagement now lives in AD; the student progress summary ships here when the AI engagement analysis (Dev B M9) lands.

## M8 — Accounts: OAuth, profile, email · _Phase 6_

- [ ] Google OAuth (authlib) alongside password auth; account linking
- [ ] Profile / settings page (display name, avatar upload, password change)
- [ ] Email notifications (Resend): class reminder, assignment due, "summary ready" · **seam:** "summary ready" triggered by Dev B's post-meeting pipeline

**DoD:** sign in with Google; edit profile; reminder emails fire via a Celery beat schedule.

## M9 — Responsive / dark / PWA · _Phase 6_ (admin panel → **AD**)

- [ ] ~~Admin panel: user management, course overview, system metrics~~ → **AD** (Members/Overview)
- [ ] Mobile-responsive dashboard + bottom-sheet patterns
- [ ] Dark/light mode (token-driven)
- [ ] PWA manifest + service worker (offline notice for scheduled classes)

**DoD:** dashboard usable at mobile widths; theme toggle persists; installable PWA.

## MP — Production hardening (shared with Dev B) · _Phase 5_

Dev A slice:
- [ ] Sentry (frontend); CSP headers; OWASP checklist for LMS routes
- [ ] GitHub Actions production deploy (frontend → Vercel) with manual approval gate
- [ ] Lighthouse/perf budget in CI

**DoD (shared):** production deploy passes a 500-student load test (owned jointly); runbook covers deploy/rollback/restore. See Dev B's MP for the realtime/infra half.

---

### Conventions
- Branch from `main`, PR back to `main`. **Signed commits** under your identity; no co-author trailers.
- **Commit hygiene:** commit freely on the branch; **squash to logical signed commits before merge** (one per small PR). Don't leave "fix typo" commits on `main`.
- One milestone per PR (split if large). Update the status table when a PR merges.
- Any change to a **shared** shape (User/ClassSession/schemas/socket events/read-models) → flag in the PR and tell Dev B.
