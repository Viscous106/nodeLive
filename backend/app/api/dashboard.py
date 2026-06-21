"""Dashboard aggregate stats + student progress."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.assignment import Assignment, Submission, SubmissionStatus
from app.models.attendance import Meeting, WatchProgress
from app.models.course import ClassSession, Course, Enrollment, SessionStatus
from app.models.user import User
from app.schemas.progress import (
    AssignmentProgressItem,
    CourseProgressItem,
    ProgressOut,
    SessionProgressItem,
)

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/stats")
async def dashboard_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    graded = await db.scalar(
        select(func.count())
        .select_from(Submission)
        .where(
            Submission.user_id == user.id,
            Submission.status == SubmissionStatus.GRADED,
        )
    )
    total = await db.scalar(
        select(func.count())
        .select_from(Submission)
        .where(Submission.user_id == user.id)
    )
    courses = await db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .where(Enrollment.user_id == user.id)
    )
    return {
        "assignmentsGraded": int(graded or 0),
        "assignmentsTotal": int(total or 0),
        "coursesEnrolled": int(courses or 0),
    }


@router.get("/me/progress", response_model=ProgressOut)
async def my_progress(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgressOut:
    # 1. Enrolled courses
    course_ids = list(
        await db.scalars(
            select(Enrollment.course_id).where(Enrollment.user_id == user.id)
        )
    )
    if not course_ids:
        return ProgressOut(
            courses=[],
            assignments_total=0,
            assignments_submitted=0,
            assignments_graded=0,
        )

    # 2. Course rows
    courses = {
        c.id: c
        for c in await db.scalars(
            select(Course).where(Course.id.in_(course_ids))
        )
    }

    # 3. Assignments for enrolled courses
    assignments = list(
        await db.scalars(
            select(Assignment)
            .where(Assignment.course_id.in_(course_ids))
            .order_by(Assignment.created_at)
        )
    )
    assignment_ids = [a.id for a in assignments]

    # 4. User's submissions
    subs_by_aid: dict[str, Submission] = {}
    if assignment_ids:
        for s in await db.scalars(
            select(Submission).where(
                Submission.assignment_id.in_(assignment_ids),
                Submission.user_id == user.id,
            )
        ):
            subs_by_aid[s.assignment_id] = s

    # 5. Sessions for enrolled courses
    sessions = list(
        await db.scalars(
            select(ClassSession)
            .where(ClassSession.course_id.in_(course_ids))
            .order_by(ClassSession.scheduled_at)
        )
    )

    # 6. Watch progress for ENDED sessions that have a stored recording
    ended_with_zoom = [
        s
        for s in sessions
        if s.zoom_meeting_id and s.status == SessionStatus.ENDED
    ]
    watch_by_session_id: dict[str, float] = {}
    if ended_with_zoom:
        zoom_mid_set = {s.zoom_meeting_id for s in ended_with_zoom}
        meetings = list(
            await db.scalars(
                select(Meeting).where(
                    Meeting.zoom_meeting_id.in_(zoom_mid_set),
                    Meeting.recording_status == "stored",
                )
            )
        )
        meeting_by_mid = {m.zoom_meeting_id: m for m in meetings}
        zoom_uuids = [m.zoom_uuid for m in meetings]
        if zoom_uuids:
            watch_by_zuuid: dict[str, WatchProgress] = {
                w.zoom_uuid: w
                for w in await db.scalars(
                    select(WatchProgress).where(
                        WatchProgress.zoom_uuid.in_(zoom_uuids),
                        WatchProgress.user_id == user.id,
                    )
                )
            }
            for s in ended_with_zoom:
                m = meeting_by_mid.get(s.zoom_meeting_id)
                if m:
                    wp = watch_by_zuuid.get(m.zoom_uuid)
                    watch_by_session_id[s.id] = (
                        wp.percent_complete if wp else 0.0
                    )

    # 7. Build per-course output
    assignments_by_course: dict[str, list[Assignment]] = {}
    for a in assignments:
        assignments_by_course.setdefault(a.course_id, []).append(a)

    sessions_by_course: dict[str, list[ClassSession]] = {}
    for s in sessions:
        sessions_by_course.setdefault(s.course_id, []).append(s)

    course_items: list[CourseProgressItem] = []
    for cid in course_ids:
        c = courses.get(cid)
        if c is None:
            continue

        a_items = [
            AssignmentProgressItem(
                id=a.id,
                title=a.title,
                max_points=a.max_points,
                due_at=a.due_at,
                status=subs_by_aid[a.id].status if a.id in subs_by_aid else None,
                grade=subs_by_aid[a.id].grade if a.id in subs_by_aid else None,
                feedback=(
                    subs_by_aid[a.id].feedback if a.id in subs_by_aid else None
                ),
                submitted_at=(
                    subs_by_aid[a.id].submitted_at if a.id in subs_by_aid else None
                ),
            )
            for a in assignments_by_course.get(cid, [])
        ]

        s_items = [
            SessionProgressItem(
                id=s.id,
                title=s.title,
                session_status=s.status,
                scheduled_at=s.scheduled_at,
                watch_percent=watch_by_session_id.get(s.id),
            )
            for s in sessions_by_course.get(cid, [])
        ]

        course_items.append(
            CourseProgressItem(
                id=c.id,
                title=c.title,
                assignments=a_items,
                sessions=s_items,
            )
        )

    # 8. Summary
    all_a = [item for ci in course_items for item in ci.assignments]
    total = len(all_a)
    submitted = sum(1 for a in all_a if a.status is not None)
    graded_count = sum(1 for a in all_a if a.status == SubmissionStatus.GRADED)
    grades = [a.grade for a in all_a if a.grade is not None]
    avg_grade = round(sum(grades) / len(grades), 1) if grades else None

    return ProgressOut(
        courses=course_items,
        assignments_total=total,
        assignments_submitted=submitted,
        assignments_graded=graded_count,
        avg_grade=avg_grade,
    )
