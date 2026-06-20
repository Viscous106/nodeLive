"""Wire a Zoom meeting id to an existing class session — operator tooling.

    python -m scripts.set_meeting <session_id> <zoom_meeting_id>

Run in the Render Shell to point a seeded session at a real Zoom meeting before
scheduling one through the admin panel. Pass an empty string to clear the field.
"""

import asyncio
import sys

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.course import ClassSession


async def set_meeting(session_id: str, zoom_id: str) -> None:
    async with AsyncSessionLocal() as db:
        cs = await db.scalar(select(ClassSession).where(ClassSession.id == session_id))
        if cs is None:
            print(f"No session with id {session_id!r}.")
            raise SystemExit(1)
        cs.zoom_meeting_id = zoom_id or None
        await db.commit()
        print(f"✓ session {session_id!r} → zoom_meeting_id = {cs.zoom_meeting_id!r}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python -m scripts.set_meeting <session_id> <zoom_meeting_id>")
        raise SystemExit(2)
    asyncio.run(set_meeting(sys.argv[1], sys.argv[2]))
