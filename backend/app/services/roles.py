"""Role + membership service — the single place role writes happen.

During expand-contract, a user's role lives in two places: the new
`Membership.role` (future source of truth) and the legacy `User.role` mirror
(still read by existing guards, `UserOut`, and the frontend). Every role
mutation MUST go through `assign_role` so the two never drift.

Single-org for now: `get_or_create_default_org` is the seam that later becomes
"the active org from the session".
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.org import DEFAULT_ORG_SLUG, Membership, Organization
from app.models.user import User, UserRole


async def get_or_create_default_org(db: AsyncSession) -> Organization:
    """The single org everything is scoped to (idempotent).

    The expand migration inserts it for the deployed instance; this get-or-create
    keeps tests and fresh databases working without a data migration.
    """
    org = await db.scalar(
        select(Organization).where(Organization.slug == DEFAULT_ORG_SLUG)
    )
    if org is None:
        org = Organization(name="linkHQ", slug=DEFAULT_ORG_SLUG)
        db.add(org)
        await db.flush()
    return org


async def get_or_create_membership(
    db: AsyncSession, user: User, org: Organization | None = None
) -> Membership:
    """The user's membership in `org` (default org if omitted).

    Lazily backfills from the `User.role` mirror if absent, so a user created
    before AF (or in a test that only set `users.role`) still resolves cleanly.
    """
    if org is None:
        org = await get_or_create_default_org(db)
    membership = await db.scalar(
        select(Membership).where(
            Membership.user_id == user.id, Membership.org_id == org.id
        )
    )
    if membership is None:
        membership = Membership(user_id=user.id, org_id=org.id, role=user.role)
        db.add(membership)
        await db.flush()
    return membership


async def assign_role(
    db: AsyncSession,
    user: User,
    role: UserRole,
    org: Organization | None = None,
) -> Membership:
    """Set a user's role on BOTH the membership and the `User.role` mirror.

    Flushes but does not commit — the caller owns the transaction boundary.
    """
    if org is None:
        org = await get_or_create_default_org(db)
    membership = await get_or_create_membership(db, user, org)
    membership.role = role
    user.role = role  # keep the legacy mirror in sync
    await db.flush()
    return membership


async def count_org_admins(db: AsyncSession, org: Organization) -> int:
    """How many ADMIN memberships the org has (last-admin guard for AD)."""
    return await db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.org_id == org.id, Membership.role == UserRole.ADMIN)
    )


async def maybe_bootstrap_admin(db: AsyncSession, user: User) -> bool:
    """Auto-grant ADMIN to a configured bootstrap email (no-shell first admin).

    Lets the very first admin exist on a deployed instance without shell access
    to run `set_role`: the moment a `BOOTSTRAP_ADMIN_EMAILS` address signs up or
    logs in, it's promoted. Idempotent — only writes when not already an admin
    on both the membership and the mirror. Returns whether a promotion happened.
    """
    if user.email.lower() not in settings.bootstrap_admin_emails:
        return False
    membership = await get_or_create_membership(db, user)
    if membership.role is UserRole.ADMIN and user.role is UserRole.ADMIN:
        return False
    await assign_role(db, user, UserRole.ADMIN)
    return True
