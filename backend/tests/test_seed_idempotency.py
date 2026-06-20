"""Seed idempotency against a partial / legacy DB.

The deploy crashed with `duplicate key ... ix_users_email` because the seed
guarded on user *id* while the unique constraint is on *email*: a legacy row
with a seed email but a different id slipped past the id check and got
re-inserted. This reproduces that exact state and asserts the seed reconciles
it instead of crashing.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.security import hash_password
from app.models.user import User, UserRole


@pytest.fixture
def seed_on_test_db(engine, monkeypatch):
    """Point the seed script's own session factory at the test database."""
    import scripts.seed as seed_mod

    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(seed_mod, "AsyncSessionLocal", maker)
    return seed_mod


async def _email_count(session, email: str) -> int:
    return await session.scalar(
        select(func.count()).select_from(User).where(User.email == email)
    )


async def test_seed_reconciles_legacy_email_with_different_id(session, seed_on_test_db):
    # Legacy partial state: a student with the seed email but an OLD id, and no
    # instructor row yet — exactly what the failing deploy's DB looked like.
    session.add(
        User(
            id="legacy-uuid-1",
            email="student1@linkhq.dev",
            hashed_password=hash_password("password123"),
            display_name="Legacy Student",
            role=UserRole.STUDENT,
        )
    )
    await session.commit()

    # Must NOT raise a duplicate-email IntegrityError.
    await seed_on_test_db.seed()

    # The legacy row was reused, not duplicated.
    assert await _email_count(session, "student1@linkhq.dev") == 1
    # And the rest of the seed completed (instructor + second student exist).
    assert await _email_count(session, "instructor@linkhq.dev") == 1
    assert await _email_count(session, "student2@linkhq.dev") == 1


async def test_seed_is_repeatable(session, seed_on_test_db):
    # Running twice on a fresh DB stays a no-op the second time (no crash, no
    # duplicate emails).
    await seed_on_test_db.seed()
    await seed_on_test_db.seed()
    assert await _email_count(session, "instructor@linkhq.dev") == 1
    assert await _email_count(session, "student1@linkhq.dev") == 1
