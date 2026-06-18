# Milestones — Dev A · Dashboard & LMS Core (`feat/dashboard`)

Owner: **OfficialAbhinavSingh**
Detail plan: [`docs/branch-A-dashboard.md`](docs/branch-A-dashboard.md) · Master plan: [`plan.md`](plan.md)

Each milestone = one PR into `main` (small, reviewed, green CI). Check items as
they land. A milestone is **Done** only when its Definition of Done holds and the
PR is merged.

---

## M0 — Auth + Session Contract ✅ DONE (PR #2)

The shared interface Dev B depends on. Shipped first so live-meeting unblocks.

- [x] `User` model + `UserRole`; Argon2id hashing; HS256 JWT in HttpOnly cookie
- [x] `POST /api/auth/signup|login|logout`, `GET /api/auth/me`
- [x] `get_current_user` + `require_role` dependencies
- [x] `Course` + `ClassSession` + `SessionStatus`
- [x] `GET /api/sessions/:id` (auth), `PATCH /api/sessions/:id` (host/instructor)
- [x] Alembic migration 001 (reversible) + `scripts/seed.py`
- [x] 16 tests (TDD, real Postgres), ruff + CI green

**DoD:** ✅ contract frozen; Dev B can read sessions and flip status.

---

## M1 — App shell & design system

- [ ] Tailwind tokens + Source Sans Pro; shadcn init (Button, Card, Badge, Skeleton, Dialog, Dropdown)
- [ ] `TopNav`, `SideDrawer` (animated), `DashboardLayout` (content + right sidebar slot)
- [ ] `LoginPage` + `SignupPage` wired to `/api/auth`; Zustand `useAuth` + React Query
- [ ] React Router with auth guard (`/` → dashboard if authed else login)

**DoD:** login → dashboard redirect works against the real backend; protected
routes bounce unauthenticated users; `npm run build` green.

## M2 — Dashboard page

- [ ] Backend: `GET /api/sessions?status=`, `GET /api/sessions/this-week`, `GET /api/courses`, `GET /api/dashboard/widgets`
- [ ] `TimetableSection` + `DateTabStrip` + `ClassCard`
- [ ] `ContinueWatchingSection` + `VideoCard` (progress bar)
- [ ] `DashboardSidebar`: `PerformanceWidget`, `NoticeBoardWidget`, `YearRevisitedBanner`
- [ ] `useDashboard` query hooks; loading skeletons; empty states

**DoD:** dashboard renders seeded data end-to-end; skeletons on every fetch;
empty states for no-classes/no-sessions; pytest covers new endpoints.

## M3 — Session detail page

- [ ] Backend: `GET /api/sessions/:id/similar`
- [ ] `SessionDetailPage` (`/session/:id`) + breadcrumb
- [ ] `UpcomingSessionHero` ("Join Session" → `/live/:id`)
- [ ] `SessionTabBar` (Feedback locked until ENDED), `SimilarSessionsRow`

**DoD:** dashboard → session detail → Join routes to the live URL; tabs gate by
status; tests for `/similar`.

## M4 — Polish & hardening

- [ ] Error boundaries per page; full skeleton/empty coverage
- [ ] Auth session refresh / 401 handling in the API client
- [ ] Accessibility pass (focus, labels, keyboard nav on drawer/dropdown)
- [ ] Tests for all new routes; ruff + pytest + build green

**DoD:** clean CI; reviewed; no console errors; desktop layout matches design ref.

---

### Conventions
- Branch from `main`, PR back to `main`; signed commits under your identity.
- Keep PRs scoped to one milestone (split if large).
- Any change to a **shared** shape (User/ClassSession/schemas) → flag in the PR and tell Dev B.
