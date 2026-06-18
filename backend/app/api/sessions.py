"""Session routes consumed by the live-meeting side.

GET is open to any authenticated user; PATCH is restricted to the session's
host or an instructor/admin (Dev B flips status to LIVE/ENDED).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.course import ClassSession
from app.models.user import User, UserRole
from app.schemas.session import ClassSessionOut, ClassSessionPatch

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _get_or_404(db: AsyncSession, session_id: str) -> ClassSession:
    cs = await db.get(ClassSession, session_id)
    if cs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return cs


@router.get("/{session_id}", response_model=ClassSessionOut)
async def get_session(
    session_id: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClassSession:
    return await _get_or_404(db, session_id)


@router.patch("/{session_id}", response_model=ClassSessionOut)
async def patch_session(
    session_id: str,
    body: ClassSessionPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClassSession:
    cs = await _get_or_404(db, session_id)

    is_privileged = user.role in (UserRole.INSTRUCTOR, UserRole.ADMIN)
    if user.id != cs.host_id and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the host or an instructor can modify this session",
        )

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(cs, field, value)
    await db.commit()
    await db.refresh(cs)
    return cs
