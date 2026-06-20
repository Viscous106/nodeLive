# Admin Dashboard (+ Organizations & Memberships foundation)

**Date:** 2026-06-20
**Status:** Approved design → ready for implementation plan
**Owner:** Cross-cutting — **coordinate with Dev A** (consolidates M7 analytics + M9 admin);
identity foundation overlaps M8.

## Problem

There is no admin surface. Roles are a global `User.role` with no assignment
path; attendance data (M6) has no viewer; sessions can only be created via API;
there's no overview. We want one **Admin Dashboard** where an org admin manages
**members & roles, sessions, attendance, and an overview** — built on a
multi-tenant-ready identity model.

## Two deliverables

1. **Foundation — Organizations & Memberships** (Part A). Prerequisite: "admin"
   is an org role, everything is org-scoped.
2. **Admin Dashboard** (Part B) — four tabs built on the foundation.

Operate as a **single org for now** (no cross-org isolation/switcher/email yet).

---

## Part A — Organizations & Memberships (foundation)

Add a `Membership` (user ↔ org ↔ role) as the management surface and the
**future** source of truth. Keep `User.role` as a synced mirror during the
transition (**expand-contract**) so Dev A's code, the frontend, and existing
guards/tests keep working unchanged.

### Data model (`backend/app/models/org.py`)
Reuse the existing `UserRole` enum (`STUDENT|INSTRUCTOR|ADMIN`) as the membership role.
- **`Organization`**: `id`, `name`, `slug` (unique), `created_at`.
- **`Membership`**: `id`, `user_id` (FK CASCADE), `org_id` (FK CASCADE),
  `role: UserRole`, `created_at`; `UniqueConstraint(user_id, org_id)`.
- **`Invitation`**: `id`, `org_id`, `email` (indexed), `role`, `token` (unique),
  `status` (`PENDING|ACCEPTED|REVOKED`), `invited_by`, `created_at`,
  `expires_at`, `accepted_at`.

### Migration strategy — **expand-contract** (non-breaking; Dev A is live)
Because `User.role` is a frozen shared shape read by Dev A's code, the frontend,
and every existing guard/test, we **do not drop it now**. AF is purely additive:

- **Expand (this milestone):** one reversible Alembic revision creates the 3
  tables, inserts a **default org** (`slug="default"`), and backfills
  `Membership(user, default_org, role=users.role)` for every existing user.
  **`users.role` stays** as a synced mirror.
- **Sync:** every role mutation (admin promote, invite-accept signup,
  `set_role`) goes through one service that writes **both** `membership.role`
  **and** `users.role` (trivial while single-org). So legacy readers stay correct.
- **Contract (later, its own migration):** once all readers use membership, drop
  `users.role`. Out of scope for AF.

### Auth (`backend/app/auth/deps.py`) — additive only
- `get_current_user`, existing `require_role`, `live._is_privileged`,
  `assignments._instructor`, `me`/`login`/`signup`, and `UserOut.role` are **left
  unchanged** — they keep reading `users.role` (still present + synced). No
  atomic swap, nothing for Dev A to coordinate-merge.
- **New, used only by the admin surface:**
  - `get_default_org(db)` (single-org seam; later → active-org-from-session).
  - `get_current_membership(user, db)` → membership in the default org.
  - **`require_org_role(*roles)`** → 403 unless the membership role matches.
- Migrating the legacy guards to membership happens in the **contract** step, not here.

### Provisioning (invite + promote)
- All role writes go through **one service** that updates `membership.role` **and**
  the `users.role` mirror together (keeps legacy readers correct).
- `POST /api/auth/signup` gains optional `inviteToken`: valid token + **signup
  email matches the invite email** → membership + mirror with the invited role +
  mark ACCEPTED; otherwise STUDENT in the default org.
- Invites are **email-locked** (shareable link, but only the invited email accepts).

### Bootstrap
Seed creates the default org + makes the seeded instructor an org ADMIN (writes
membership + mirror). `scripts/set_role` does the same (operator escape hatch).
Note: on the **already-deployed** instance, the backfill makes the existing
instructor's membership `INSTRUCTOR` — promote someone to `ADMIN` via `set_role`
once, or there's no admin.

---

## Part B — Admin Dashboard

`/admin` route, **ADMIN-only**. New `backend/app/api/admin.py`, every route
`require_org_role(ADMIN)`. Four tabs:

### 1. Overview — `GET /api/admin/overview`
Counts (members by role, courses, sessions by status), recent activity (latest
sessions / signups), engagement snapshot (top leaderboard, quiz/poll
participation totals). Aggregation queries; leaderboard query already exists.

### 2. Members & Roles
- `GET /api/admin/members` → `[{userId, email, displayName, role, joinedAt}]`
- `PATCH /api/admin/members/{userId}/role` `{role}` — guard: never drop the org
  to **zero admins** (block demoting the last admin).
- `POST /api/admin/invitations` `{email, role}` → `{inviteUrl}` (token, +7d);
  409 if already a member · `GET` list · `DELETE /{id}` revoke.
- `GET /api/invitations/{token}` (**public**) → `{orgName, role, email}` for the
  signup screen.

### 3. Sessions (schedule & manage)
- `GET /api/admin/sessions` (list, filter by status) · reuse `POST/PATCH
  /api/sessions` (also allow ADMIN, not just host) · `POST
  /api/admin/sessions/{id}/cancel` (status → CANCELLED).
- v1 takes a **manually-entered/placeholder `zoom_meeting_id`**. Auto-creating a
  real Zoom meeting via S2S create-meeting is a **fast-follow integration**.

### 4. Attendance reports
- `GET /api/admin/attendance/sessions/{id}` → per-participant present-time + %
  from M6's `attendance_final` (joined to the session's duration).
- `GET /api/admin/attendance/students/{userId}` → that user's attendance across
  the org's sessions.
- **Renders empty until real Zoom is wired** — `attendance_final` is fed by the
  M6 reconcile job, which needs real webhooks + Reports-API creds. The data path
  is correct; it's just unfed in the demo. Watch-time (M7 recordings) is out of scope.

### Frontend
- `/admin` admin-only area with a tab nav (Overview / Members / Sessions /
  Attendance). React Query hooks per endpoint; empty/loading states throughout.
- Signup reads `?invite=<token>`, shows "Joining {org} as {role}", passes it through.

---

## Deferrals (explicit YAGNI)
- Cross-org data isolation (`org_id` on Course/Session/etc.), org switcher,
  super-admin UI, email delivery of invites — later multi-tenancy milestone.
- Real Zoom-meeting auto-provisioning (S2S create-meeting) — fast-follow.
- Watch-time analytics — needs M7 recording ingest (not built).

## Build phasing (instructor access first)
1. **Foundation + Members & Roles tab** → unblocks instructor access.
2. **Sessions** tab.
3. **Attendance** reports tab.
4. **Overview + engagement** tab.

## Testing
- Backfill migration round-trips (memberships created from `users.role`; `users.role`
  retained); role mutation keeps `membership.role` and `users.role` in sync.
- `require_org_role` gating (403s for non-admin); invite→signup-with-matching-token
  assigns role, mismatched/expired rejected; promote changes role, last-admin
  demotion blocked.
- **Existing live/assignment/auth tests untouched** (still read the synced
  `users.role`) — confirms AF is non-breaking.
- Admin read endpoints return shaped data + correct empty states when attendance
  is unfed.

## Milestone placement (plan change)
Add to the roadmap:
- **Foundation milestone — "Organizations & Memberships"** (identity; adds
  org/membership, keeps `users.role` as a mirror — dropped in a later contract
  step). Prerequisite; overlaps M8.
- **"Admin Dashboard" milestone** (the 4 tabs) — **absorbs/extends Dev A's M7
  (analytics) and M9 (admin panel)** rather than duplicating them.

## Shared seam — coordinate with Dev A (real teammate)
AF is **additive**: `User.role` stays (synced mirror), so Dev A's `user.role`
readers and any in-flight branches keep working — no atomic break. Still flag the
new org/membership models + admin surface to Dev A (overlaps M7/M8/M9), and agree
when to do the later **contract** step (drop `users.role`, migrate readers).
Frontend `types/index.ts` `User.role` stays.
