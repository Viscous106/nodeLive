# Production Fix Plan

Fixes for nodeLive live deployment. All env vars already configured on Render —
remaining work is purely code changes. Ordered P0 → P3.

---

## Priority Key

| Level | Meaning |
|---|---|
| **P0** | Core feature completely broken — fix first |
| **P1** | Feature partially works but incorrectly — production correctness |
| **P2** | Works but fragile — reliability / resilience |
| **P3** | UX polish |

---

## P0 — Attendance Pipeline Broken

### Fix 1 · Webhook must flip `ClassSession.status → ENDED`

**Root cause:** `_mark_ended()` in `webhooks.py` updates `Meeting.ended_at` but
never touches `ClassSession.status`. Sessions stay stuck as `LIVE` after the Zoom
meeting ends. The Attendance tab filters for `status=ENDED` → dropdown is always
empty.

**File:** `backend/app/api/webhooks.py`

In `_mark_ended()`, after setting `meeting.ended_at`:
- Join `ClassSession` on `zoom_meeting_id`
- If `cs.status == LIVE` → set `cs.status = ENDED`

---

### Fix 2 · Add `POST /admin/sessions/{id}/end` (manual fallback)

**Root cause:** No way to manually end a session. If the Zoom webhook misses
(network blip), the session is permanently stuck as `LIVE` with no recovery path
short of a raw DB query.

**File:** `backend/app/api/admin.py`

New endpoint:
```
POST /admin/sessions/{session_id}/end
Auth: admin only
Response: ClassSessionOut
```

- 404 if session not found
- 409 if session is already `ENDED` or `CANCELLED`
- Sets `cs.status = ENDED`, `cs.ended_at = now(UTC)`
- If `zoom_meeting_id` set + a `Meeting` row exists → trigger
  `attendance_tasks.schedule_reconcile(meeting.zoom_uuid)`

---

### Fix 3 · "End Session" button in admin Sessions tab

**Root cause:** No UI entry point for Fix 2.

**File:** `frontend/src/hooks/useAdmin.ts`

Add `useEndSession()` mutation:
- `POST /api/admin/sessions/:id/end`
- On success: invalidate `['admin', 'sessions']` (broad key catches the `ENDED`
  sub-query used by AttendanceTab), show success toast

**File:** `frontend/src/components/admin/SessionsTab.tsx`

Add a green checkmark button (`CheckSquare` from lucide-react) per row:
- Visible only for `LIVE` sessions (disabled for all other statuses)
- `onClick` → `useEndSession().mutate(session.id)`

---

## P1 — Production Correctness

### Fix 4 · Overview member count not scoped to org

**Root cause:** `get_overview()` counts `SELECT COUNT(*) FROM users` — every user
in the DB, not members of the calling org. Wrong on any multi-org deployment.

**File:** `backend/app/api/admin.py`

```diff
- members_count = await db.scalar(select(func.count()).select_from(User))
+ members_count = await db.scalar(
+     select(func.count())
+     .select_from(Membership)
+     .where(Membership.org_id == membership.org_id)
+ )
```

---

### Fix 5 · Add `ended_at` column to `ClassSession`

**Root cause:** No `ended_at` on `ClassSession`. Attendance analytics (actual
session length vs scheduled duration) requires it, and the janitor task (Fix 6)
needs it for accurate cutoffs.

**File (new migration):** `backend/alembic/versions/<rev>_add_session_ended_at.py`

```python
op.add_column('class_sessions',
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True)
)
```

**File:** `backend/app/models/course.py`

```python
ended_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

Set `cs.ended_at` in:
- `webhooks.py` `_mark_ended()` → `cs.ended_at = _dt(ended)`
- `admin.py` `end_session()` → `cs.ended_at = datetime.now(UTC)`

---

### Fix 6 · Celery janitor: auto-end stale LIVE sessions

**Root cause:** If a host disconnects without ending the session and the webhook
never fires, the session is stuck `LIVE` indefinitely.

**File (new):** `backend/app/workers/session_tasks.py`

Celery task `sessions.janitor`:
- Finds sessions with `status=LIVE` and `scheduled_at < now - 2h`
- Sets `status = ENDED` for all matches
- Returns count of rows fixed

**File:** `backend/app/workers/celery_app.py`

- Add `"app.workers.session_tasks"` to `include`
- Add beat schedule: `sessions.janitor` every 3600s (hourly)

**File:** `backend/start.sh`

Start `celery beat` alongside the worker so scheduled tasks actually fire:

```sh
celery -A app.workers.celery_app beat --loglevel=warning &
celery -A app.workers.celery_app worker --pool=solo --concurrency=1 --loglevel=warning &
```

---

### Fix 7 · `list_all_sessions` not scoped to org

**Root cause:** `GET /api/admin/sessions` returns all `ClassSession` rows in the
DB regardless of org. Harmless now (single org), wrong long-term.

**File:** `backend/app/api/admin.py`

Add a subquery filter: only include sessions whose `course_id` belongs to a course
associated with the calling org's enrolled members.

---

## P2 — Reliability & Resilience

### Fix 8 · Zoom token cache is process-local

**Root cause:** `zoom_auth.py` caches the S2S OAuth token in a plain Python dict.
Cache is lost on restart and not shared across multiple Celery workers.

**File:** `backend/app/utils/zoom_auth.py`

Replace in-memory dict with Redis (`REDIS_URL` already in config):
- Key: `nodelive:zoom:access_token`
- TTL: `expires_in - 60` seconds
- Use `redis.from_url(settings.REDIS_URL, decode_responses=True)`

---

### Fix 9 · Webhook handler swallows all errors silently

**Root cause:**
```python
except Exception:
    await db.rollback()
return JSONResponse({"status": "ok"})
```
Any handler error is silently discarded — bugs are invisible in production logs.

**File:** `backend/app/api/webhooks.py`

```diff
+ import logging
+ logger = logging.getLogger(__name__)

  except Exception:
      await db.rollback()
+     logger.exception("webhook handler error for event %s", event.get("event"))
```

---

### Fix 10 · Attendance reconcile has no retry on Zoom API failure

**Root cause:** `reconcile_attendance` Celery task has no `autoretry_for` or
`max_retries`. A transient Zoom 503 causes permanent task failure and lost
attendance data.

**File:** `backend/app/workers/attendance_tasks.py`

```diff
- @celery_app.task(name="attendance.reconcile")
+ @celery_app.task(
+     name="attendance.reconcile",
+     autoretry_for=(Exception,),
+     max_retries=5,
+     retry_backoff=True,
+     retry_backoff_max=300,
+ )
```

---

### Fix 11 · No "LIVE" indicator on dashboard ClassCards

**Root cause:** Dashboard shows session cards but no visual cue when a session
is currently in progress. Students can miss that a class is happening now.

**File:** `frontend/src/components/dashboard/ClassCard.tsx`

- Add pulsing `LIVE` badge when `session.status === 'LIVE'`
- Change link target for LIVE sessions: `/live/:id` (join directly) instead of
  `/session/:id` (detail page)
- Change link label: `"Join now →"` for LIVE, `"View details"` otherwise

---

## P3 — UX Polish

### Fix 12 · Past sessions tab incorrectly includes LIVE sessions

**Root cause:** The `status=past` query uses:
```python
or_(
    ClassSession.scheduled_at < now,
    ClassSession.status == SessionStatus.ENDED,
)
```
The first branch matches any session whose scheduled time has passed — including
sessions that are still `LIVE`.

**File:** `backend/app/api/sessions.py`

Exclude LIVE from the past filter:
```python
or_(
    ClassSession.status == SessionStatus.ENDED,
    ClassSession.status == SessionStatus.CANCELLED,
    and_(
        ClassSession.scheduled_at < now,
        ClassSession.status != SessionStatus.LIVE,
    ),
)
```

---

## File Change Summary

### Backend

| Priority | File | Change |
|---|---|---|
| P0 | `app/api/webhooks.py` | `_mark_ended()` flips ClassSession.status → ENDED |
| P0 | `app/api/admin.py` | Add `POST /admin/sessions/{id}/end` |
| P1 | `app/api/admin.py` | Fix overview member count to filter by org |
| P1 | `alembic/versions/<rev>_add_session_ended_at.py` | New migration |
| P1 | `app/models/course.py` | Add `ended_at` to ClassSession |
| P1 | `app/workers/session_tasks.py` | New janitor task |
| P1 | `app/workers/celery_app.py` | Register janitor + beat schedule |
| `start.sh` | P1 | Start celery beat alongside worker |
| P1 | `app/api/admin.py` | Scope list_all_sessions to org |
| P2 | `app/utils/zoom_auth.py` | Redis-backed token cache |
| P2 | `app/api/webhooks.py` | Log exceptions instead of swallowing |
| P2 | `app/workers/attendance_tasks.py` | Auto-retry with exponential backoff |
| P3 | `app/api/sessions.py` | Exclude LIVE sessions from past filter |

### Frontend

| Priority | File | Change |
|---|---|---|
| P0 | `src/hooks/useAdmin.ts` | Add `useEndSession()` mutation |
| P0 | `src/components/admin/SessionsTab.tsx` | Add "End Session" button for LIVE rows |
| P2 | `src/components/dashboard/ClassCard.tsx` | LIVE badge + "Join now" link |

---

## Verification Plan

### P0 (manual, each fix in order):
1. Deploy backend → Admin → Sessions tab
2. LIVE session → click "End Session" → status flips to ENDED
3. Admin → Attendance tab → ended session appears in dropdown
4. Select it → enrolled students listed (all 0s until real Zoom meeting runs)
5. Run real Zoom test → webhook fires → Celery reconcile → attendance populates

### P1:
- Overview → Members count matches actual org member count
- Let session run 2h past scheduled time with no end → janitor fires → status
  flips to ENDED within 1 hour

### Automated tests:
```bash
cd backend && pytest tests/ -x -v && ruff check . && ruff format --check .
cd frontend && npm run build
```
