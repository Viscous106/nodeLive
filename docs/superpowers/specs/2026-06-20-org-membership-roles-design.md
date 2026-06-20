# Organizations & Memberships — role/access redesign

**Date:** 2026-06-20
**Status:** Approved design → ready for implementation plan
**Owner:** Dev B (identity/access) — **coordinate with Dev A** (M8 accounts / M9 admin)

## Problem

Roles are a **global** `User.role` field (`STUDENT | INSTRUCTOR | ADMIN`) that
defaults to `STUDENT` on signup, with **no way to assign roles** except the seed
or a shell script. We want a clean, multi-tenant-ready way for an organization
admin to grant instructor access to lecturers — via invite *and* promotion.

## Decision

Move role off `User` onto a **`Membership`** (user ↔ org ↔ role). Membership is
the source of truth and the management surface. Build the model multi-tenant-
ready but **operate with a single organization for now** — no cross-org data
isolation, org-switcher, or email delivery yet.

### Goals
- A `Membership` model where role is org-scoped (foundation for many orgs).
- Org admins grant the INSTRUCTOR (or ADMIN) role by **invite link** and by
  **promoting** an existing member.
- Existing access checks keep working; the frontend keeps reading `user.role`.

### Non-goals (YAGNI for this slice — explicitly deferred)
- Cross-org **data isolation** (`org_id` on Course/ClassSession/Enrollment/
  attendance) and an org switcher — later multi-tenancy milestone.
- **Email delivery** of invites — return a copyable link; email is M8.
- Multi-org **active-org resolution** (subdomain/session) — single default org now.
- Platform **super-admin** UI for managing orgs — later.

## Data model (`backend/app/models/org.py`)

Reuse the existing `UserRole` enum (`STUDENT|INSTRUCTOR|ADMIN`) as the membership
role — values are identical and the frontend already knows them.

- **`Organization`**: `id` (uuid str), `name`, `slug` (unique), `created_at`.
- **`Membership`**: `id`, `user_id` (FK users CASCADE), `org_id` (FK orgs
  CASCADE), `role: UserRole`, `created_at`. `UniqueConstraint(user_id, org_id)`.
- **`Invitation`**: `id`, `org_id` (FK), `email` (indexed), `role: UserRole`,
  `token` (unique), `status` (`PENDING|ACCEPTED|REVOKED`), `invited_by` (FK
  users), `created_at`, `expires_at`, `accepted_at` (nullable).

## Migration + backfill (one Alembic revision, reversible)

1. Create `organizations`, `memberships`, `invitations`.
2. Insert a **default org** (`slug="default"`, name "linkHQ").
3. For every existing user, insert `Membership(user, default_org, role=users.role)`.
4. **Drop `users.role`** (the `user_role` PG enum type stays — now used by
   `memberships.role` / `invitations.role`).

Downgrade: re-add `users.role`, backfill from the default-org membership, drop tables.

## Auth changes (`backend/app/auth/deps.py`)

- `get_current_user` unchanged (returns `User`).
- `get_default_org(db)` — fetch the `slug="default"` org (single-org seam;
  later swapped for active-org-from-session).
- `get_current_membership(user, db)` → the user's membership in the default org
  (401/403 if none).
- **`require_org_role(*roles)`** — dependency that 403s unless the current
  membership role is in `roles`. The **role portion** of every current check
  reads the membership instead of `user.role`:
  - `auth/deps.require_role(...)` callers → `require_org_role(...)`.
  - `api/assignments.py` `_instructor` → `require_org_role(INSTRUCTOR, ADMIN)`.
  - `api/live.py` `_is_privileged` is **host OR role** — keep the
    `cs.host_id == user.id` check and swap only the role half to the membership
    role (`_host_session` / `_member_session` stay; they just read membership).
- `me` / `login` / `signup` responses set `UserOut.role` from the resolved
  membership, so the **frontend keeps reading `user.role` unchanged**.

## API (all admin-gated via `require_org_role(ADMIN)` unless noted)

- `GET  /api/org/members` → `[{userId, email, displayName, role, joinedAt}]`
- `PATCH /api/org/members/{userId}/role` `{role}` → update that member's role.
  Guard: an org must never reach **zero admins** (block demoting the last admin).
- `POST /api/org/invitations` `{email, role}` → create PENDING invite (token,
  `expires_at` = +7d); returns `{inviteUrl}`. 409 if email is already a member.
- `GET  /api/org/invitations` → pending invites.
- `DELETE /api/org/invitations/{id}` → mark REVOKED.
- `GET  /api/invitations/{token}` (**public**) → `{orgName, role, email}` for the
  signup screen to show "Joining as Instructor". Invalid/expired → 404.
- `POST /api/auth/signup` gains optional `inviteToken`:
  - valid token + **signup email matches the invite email** → membership with
    the invited role; mark invite ACCEPTED.
  - no token → membership in the default org with role `STUDENT` (current behavior).

## Frontend

- **`/admin/members`** (admin-only route): member table with an inline role
  `<select>`; an Invite form (email + role) that, on submit, shows the copyable
  invite link; a pending-invites list with Revoke.
- **Signup**: read `?invite=<token>`, fetch the public preview, show "You're
  joining **{org}** as **{role}**", and pass `inviteToken` to `POST /signup`.
- `User` type keeps `role`; `me`/login responses still populate it.

## Bootstrap (first admin)

Chicken-and-egg: the admin API needs an ADMIN. The **seed** creates the default
org + makes the seeded instructor an org ADMIN. `scripts/set_role` is updated to
write the membership (the operator escape hatch).

## Testing

- Backfill migration round-trips (upgrade backfills memberships from `users.role`;
  downgrade restores `users.role`).
- `require_org_role` gating: admin-only endpoints 403 for instructor/student.
- Invite → signup-with-matching-token assigns the invited role; mismatched email
  rejected; expired/revoked token rejected.
- Promote changes role; demoting the **last admin** is blocked.
- Existing live/assignment authz still passes after the guard swap.

## Shared seam — must coordinate with Dev A

Removes `User.role` (a frozen shared shape) and adds the org/membership models +
auth deps that overlap Dev A's M8/M9. Land as a coordinated PR with Dev A, not solo.
Frontend `types/index.ts` `User.role` stays (now sourced from membership).
