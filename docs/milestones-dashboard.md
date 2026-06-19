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
| M5 Assignments & grading | Phase 3 | |
| M6 Lecture notes + recording player (+ watch-tracking UI) | Phase 3 + compliance | |
| M7 Analytics dashboards | Phase 3/4 | |
| M8 Accounts: OAuth, profile, email | Phase 6 | |
| M9 Admin panel + responsive/dark/PWA | Phase 6 | |
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

## M7 — Analytics dashboards · _Phase 3/4_

- [ ] Course analytics: attendance heatmap, completion rates (reads `attendance_final` + watch read-models)
- [ ] Instructor insights page: per-session engagement (quiz/poll participation) · **seam:** data from Dev B's leaderboard/quiz tables
- [ ] Student "Year Revisited" / progress summary (consumes Dev B's AI engagement analysis when available)

**DoD:** instructor sees real attendance/engagement for seeded sessions; queries indexed; no N+1.

## M8 — Accounts: OAuth, profile, email · _Phase 6_

- [ ] Google OAuth (authlib) alongside password auth; account linking
- [ ] Profile / settings page (display name, avatar upload, password change)
- [ ] Email notifications (Resend): class reminder, assignment due, "summary ready" · **seam:** "summary ready" triggered by Dev B's post-meeting pipeline

**DoD:** sign in with Google; edit profile; reminder emails fire via a Celery beat schedule.

## M9 — Admin panel + responsive/dark/PWA · _Phase 6_

- [ ] Admin panel: user management, course overview, system metrics (admin-gated)
- [ ] Mobile-responsive dashboard + bottom-sheet patterns
- [ ] Dark/light mode (token-driven)
- [ ] PWA manifest + service worker (offline notice for scheduled classes)

**DoD:** admin CRUD works; dashboard usable at mobile widths; theme toggle persists; installable PWA.

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
