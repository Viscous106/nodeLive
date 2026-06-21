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
| M6 Lecture notes + recording player (+ watch-tracking UI) | Phase 3 + compliance | ✅ lecture notes ✅ (PR #17); recording player + watch-tracking UI built jointly w/ Dev B M7 |
| **AF Organizations & Memberships** (foundation) | identity | ✅ done — org/membership/invitation models + backfill migration (`User.role` kept as a synced mirror), additive `require_org_role`, role-write service, invite signup |
| **AD Admin Dashboard** (members/roles, sessions, enrollments, attendance, overview) | Phase 3/4/6 | 🟡 in progress — **Members & Roles ✅** + bootstrap admin ✅ + **Sessions ✅** + **Enrollments ✅**; Attendance / Overview pending. **consolidates M7 + M9** |
| ~~M7 Analytics dashboards~~ | Phase 3/4 | → folded into **AD** (Attendance + Overview tabs) |
| M8 Accounts: OAuth, profile, email | Phase 6 | (org/membership identity foundation moves under **AF**) |
| ~~M9 Admin panel + responsive/dark/PWA~~ | Phase 6 | admin panel → **AD**; responsive/dark/PWA stay here |
| MP Production hardening (shared) | Phase 5 | 🟡 partial — backend serves the built SPA same-origin with COOP/COEP; Sentry/Vercel-CI/Lighthouse pending |

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

- [x] Backend: `GET /api/sessions?status=` (`upcoming`/`past`), `/api/sessions/this-week`, `/api/courses`, `/api/dashboard/stats` (Performance widget) (`sessions.py`, `courses.py`, `dashboard.py`)
- [x] `TimetableSection` + `DateTabStrip` + `ClassCard` (`components/dashboard/`)
- [ ] `ContinueWatchingSection` + `VideoCard` — section + card built (`VideoCard.tsx` links to the recording player), but the card shows a "Resume" label, **no watch-progress bar** yet
- [x] `DashboardSidebar`: `PerformanceWidget`, NoticeBoardWidget (empty-state), revisited banner (`DashboardSidebar.tsx`)
- [x] `useDashboard` hooks; loading skeletons (`Skeleton`); empty states ("Nothing to catch up on yet…")

**DoD:** dashboard renders seeded data end-to-end; skeletons on every fetch; empty states; pytest covers new endpoints.

## M3 — Session detail page · _Phase 0/3_

- [x] Backend: `GET /api/sessions/:id/similar` (`sessions.py:137`)
- [x] `SessionDetailPage` (`/session/:sessionId`) + "Back to dashboard" breadcrumb (`SessionDetailPage.tsx`)
- [x] `UpcomingSessionHero` ("Join" → `/live/:id`) · **seam:** route owned by Dev B (`UpcomingSessionHero.tsx:50`)
- [x] `SessionTabBar` (Feedback locked until ENDED), `SimilarSessionsRow` (`SessionTabBar.tsx:23`, `SimilarSessionsRow.tsx`)

**DoD:** dashboard → session detail → Join routes to the live URL; tabs gate by status; tests for `/similar`.

## M4 — Frontend polish & hardening · _Phase 1/2 support_

- [x] Error boundaries (`components/ErrorBoundary.tsx`, mounted in `main.tsx`); skeleton/empty coverage (M2)
- [ ] API client: **401 handling done** — `queryClient.ts` clears auth on a 401 (`onError`); toast system shipped (`stores/toastStore.ts` + `ui/Toaster.tsx`, shared w/ Dev B). **No session refresh** yet → box left open.
- [x] Accessibility pass — drawer + dropdown have `aria-*`/`role`, focus + `Escape` handling (`SideDrawer.tsx`, `ui/dropdown-menu.tsx`)
- [ ] Route-level code splitting **done** (`React.lazy` per route in `router.tsx`); Lighthouse pass on dashboard not evidenced → box left open

**DoD:** clean CI; no console errors; desktop layout matches design ref.

## M5 — Assignments & grading · _Phase 3_

- [x] Models + migration: `Assignment`, `Submission` (+ status, grade) (`models/assignment.py`, migration `64f290eb783a_assignments_submissions.py`)
- [x] `POST/GET/PATCH /api/assignments` (CRUD, instructor/admin-gated) (`api/assignments.py`)
- [ ] Submission upload → object storage (R2/S3) presigned URLs — **not implemented**; submissions are text `content: str` (`schemas/assignment.py`), no storage/presign
- [x] Student view: submit / view grade; Instructor view: grading interface (`GradeRow`) (`components/session/AssignmentTab.tsx`, `hooks/useAssignments.ts`)
- [x] pytest: authz, submission lifecycle, grade write (`tests/test_assignments.py`)

**DoD:** assign → submit → grade → view loop works; uploads stored in R2; instructor-only gates enforced.

## M6 — Lecture notes + recording player + watch-tracking UI · _Phase 3 + compliance_

- [ ] `LectureNote` model ✅ + post/list routes (`models/lecture_note.py`, `api/notes.py`); but materials are stored as an external `url` — **no R2 upload + signed download URL** yet → box left open
- [ ] Recording player page ✅ (`pages/RecordingPlayerPage.tsx`, route `/session/:sessionId/recording`); **bookmarks-as-clickable-timestamps NOT present** in the player → box left open
- [x] Watch-tracking client: reports actually-played spans → `POST /api/sessions/:id/recording/heartbeat` (`hooks/useRecording.ts`, `api/recordings.py:101`) · **seam:** union/coverage via Dev B's `intervals`/`watch.py`
- [ ] Surface watch % + attendance % on dashboard/session — backend read-model exists (`recording/watch-status`, `recordings.py:144`) but **not yet surfaced** in `VideoCard`/`SessionDetailPage`/`useDashboard` → box left open

**DoD:** play recording, seek, jump to a bookmark; watch % reflects the **union of real played spans** (seek-to-end ≠ 100%); notes download via signed URL.

## AF — Organizations & Memberships (foundation) · _identity_

Design: [`docs/superpowers/specs/2026-06-20-admin-dashboard-design.md`](superpowers/specs/2026-06-20-admin-dashboard-design.md) (Part A). **Prerequisite for AD.**

- [x] `Organization` + `Membership` (user↔org↔role, reuses `UserRole`) + `Invitation` models + reversible migration that inserts the default org and backfills memberships from `users.role` (**keeps `users.role`** as a synced mirror — expand-contract)
- [x] **Additive** `get_current_membership` / `get_default_org` / `require_org_role(*roles)` for the admin surface only; existing guards/`UserOut`/frontend untouched (still read the synced `users.role`)
- [x] One role-write service (`services/roles.py`) updates `membership.role` + the `users.role` mirror together; invite (email-locked link) honored at `POST /api/auth/signup` via `inviteToken`; seed (instructor → org ADMIN) + `set_role` write both · `count_org_admins` ready for the AD last-admin guard · **seam:** new org/membership models flagged to Dev A; the later **contract** step (drop `users.role`) is coordinated

**DoD:** ✅ non-breaking (131 tests green, existing untouched); `require_org_role` gates; invite→signup assigns role (mismatch/expired/revoked rejected); role writes sync membership + mirror; backfill migration round-trips (up→down→up clean, 1:1 backfill verified). Admin endpoints + last-admin demotion guard land in **AD**.

## AD — Admin Dashboard · _Phase 3/4/6 — consolidates M7 + M9_

Design: [`docs/superpowers/specs/2026-06-20-admin-dashboard-design.md`](superpowers/specs/2026-06-20-admin-dashboard-design.md) (Part B). `/admin`, ADMIN-only, built on **AF**. Phased: Members → Sessions → Attendance → Overview.

**Status: phase 3 of 4 shipped** — Members & Roles, no-shell bootstrap admin, the Sessions tab, and the Enrollments tab are implemented; pending commit/PR/deploy. Attendance and Overview tabs are next (no routes for them in `admin.py` yet).

- [x] **Members & Roles** tab — list members, promote/demote (last-admin guard), invite-by-link, revoke + invite-aware signup · `/api/admin/*` + `/admin` UI (12 backend tests)
- [x] **No-shell bootstrap admin** — `BOOTSTRAP_ADMIN_EMAILS` (default `abhinav.singh@scaler.com`) auto-grants ADMIN on login/signup, so the first admin exists on the deployed instance without Shell access (4 tests)
- [x] **Sessions** tab — list (all, status-filtered) / create (`POST /api/sessions`) / edit (PATCH) / cancel · `/api/admin/sessions*` + `/api/admin/courses` + tabbed `/admin` UI. Host picker lists **all members** (`useMembers`) — any member (incl. a student) can be assigned host; only the host is the Zoom host (`is_zoom_host = host_id`). Real Zoom meeting is **auto-created via S2S** when the host first clicks "Join video" (`zoom_meetings.py`); the `zoomMeetingId` field is an optional manual override.
- [x] **Enrollments** tab — list / create / remove enrollments (`EnrollmentsTab.tsx` + `GET/POST/DELETE /api/admin/enrollments`, course/instructor pickers via `/api/admin/courses` + `/api/admin/instructors`)
- [ ] **Attendance** tab — per-session + per-student from `attendance_final` (no attendance route in `admin.py`; empty until real Zoom creds feed M6 reconcile)
- [ ] **Overview** tab — counts, recent activity, engagement snapshot (no overview route in `admin.py`)

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

Dev A slice (🟡 partial):
- [x] Backend serves the built SPA same-origin on Render with COOP/COEP from the backend `cross_origin_isolation` middleware (`backend/app/main.py` — `StaticFiles` mount + SPA fallback)
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
