"""Set a user's role — admin tooling.

    python -m scripts.set_role <email> <STUDENT|INSTRUCTOR|ADMIN>

Grants a lecturer instructor (or admin) access. Until the admin panel (Dev A M9)
ships a UI, this is how roles are assigned — run it by a trusted operator (e.g.
in the Render Shell), not exposed to end users.
"""

import asyncio
import sys

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole
from app.services.roles import assign_role


async def set_role(email: str, role: str) -> None:
    try:
        new_role = UserRole(role.upper())
    except ValueError:
        valid = ", ".join(r.value for r in UserRole)
        print(f"Invalid role {role!r}. Use one of: {valid}")
        raise SystemExit(1) from None

    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"No user with email {email!r}.")
            raise SystemExit(1)
        # Writes both membership.role and the User.role mirror.
        await assign_role(db, user, new_role)
        await db.commit()
        print(f"✓ {email} is now {new_role.value}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python -m scripts.set_role <email> <STUDENT|INSTRUCTOR|ADMIN>")
        raise SystemExit(2)
    asyncio.run(set_role(sys.argv[1], sys.argv[2]))
