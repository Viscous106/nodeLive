# Branch A — Dashboard & LMS Core

**Branch:** `feat/dashboard`  
**Owner:** Dev A  
**Base branch:** `main` (foundation skeleton already merged)  
**Estimated time:** 3 days  
**Stack:** React 19 + TSX (frontend) | Python 3.12 + FastAPI (backend)  
**Design ref:** `lms-ui-research/analysis/` + `lms-ui-research/screenshots/provided/`

> **Status (verified against code, 2026-06-21):** Core LMS dashboard shell is
> **implemented end-to-end** — auth, layout/shell, dashboard page (timetable,
> continue-watching, sidebar), session detail (similar sessions, tabs), and the
> recording player + watch-tracking. Items confirmed in code are ticked below;
> a few are partials and are noted inline. Two endpoint paths drifted from the
> original plan: the combined dashboard endpoint shipped as
> `GET /api/dashboard/stats` (not `/widgets`), and course **enroll** lives under
> the admin API (`POST /api/admin/enrollments` + auto-enroll on course create),
> not `POST /api/courses/:id/enroll`. Still pending: profile/settings page,
> OAuth, email notifications, mobile/dark-mode/PWA, and MP hardening.

---

## Scope

Build the full LMS dashboard shell that replicates Scaler Academy's structure:
- Authentication (signup / login / logout)
- Dashboard page (`/dashboard`) — timetable, continue watching, right sidebar
- Session detail page (`/session/:id`) — upcoming class info, similar sessions
- Profile/settings stub

**NOT in scope for this branch:**
- Live class page (Dev B owns that)
- Code editor
- Assignment submission grading
- Leaderboard (API ready, UI stub only)

---

## Day-by-Day Task Breakdown

### Day 1 — Auth + Layout Shell

**Morning: Backend (FastAPI)**

1. `backend/app/models/user.py` — User model (SQLAlchemy 2.0)
   ```python
   class User(Base):
       __tablename__ = "users"
       id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
       email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
       hashed_password: Mapped[str] = mapped_column(String(255))
       display_name: Mapped[str] = mapped_column(String(100))
       role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.STUDENT)
       avatar_url: Mapped[str | None] = mapped_column(String(500))
       coins: Mapped[int] = mapped_column(Integer, default=0)
       created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
   ```

2. `backend/app/api/auth.py` — 4 routes:
   - `POST /api/auth/signup` — validate email+password, hash with argon2, create user, return JWT cookie
   - `POST /api/auth/login` — verify password, return JWT cookie
   - `POST /api/auth/logout` — clear cookie
   - `GET /api/auth/me` — return current user from JWT

3. `backend/app/auth/tokens.py` — `create_access_token()`, `decode_token()`, `get_current_user` dependency (see plan.md §9)

4. Run: `alembic revision --autogenerate -m "users"` + `alembic upgrade head`

**Afternoon: Frontend (React)**

5. `frontend/src/pages/LoginPage.tsx`
   ```
   Layout: centered card (480px wide), white bg, card shadow
   Logo: "nodeLive" text (bold, primary blue)
   Form: Email input, Password input, "Login" button (primary blue, full width)
   Link: "Don't have an account? Sign up"
   Error: red banner below form on failed login
   ```

6. `frontend/src/pages/SignupPage.tsx` — same layout, adds Display Name field

7. `frontend/src/hooks/useAuth.ts` — Zustand store + React Query for `/api/auth/me`
   ```ts
   interface AuthStore {
     user: User | null
     isLoading: boolean
     login: (email, password) => Promise<void>
     logout: () => Promise<void>
   }
   ```

8. `frontend/src/lib/api.ts` — fetch wrapper with credentials: 'include' (for cookie auth)

9. `frontend/src/router.tsx` — React Router v6:
   ```
   / → redirect to /dashboard if authed, else /login
   /login
   /signup
   /dashboard           (requires auth)
   /session/:sessionId  (requires auth)
   ```

**Evening: Shared Layout**

10. `frontend/src/components/layout/TopNav.tsx`:
    ```
    height: 64px, bg: white, border-bottom: 1px solid #E2E8F0
    sticky top-0 z-50
    Left: HamburgerIcon (opens drawer) + Logo "nodeLive" shield + text
    Right: CoinCounter (gold coin icon + number) | BellIcon | UserAvatarDropdown
    UserAvatarDropdown: avatar initials circle + display name + ▼ → logout option
    ```

11. `frontend/src/components/layout/SideDrawer.tsx`:
    ```
    width: 290px, height: 100vh, bg: white, fixed left-0 top-0 z-50
    box-shadow: 0 20px 60px rgba(0,0,0,0.15)
    Backdrop: fixed inset-0 bg-black/40 z-40, onClick closes drawer
    Items (with Lucide icons):
      Home (House icon)           → /dashboard
      ─── LEARN AND PRACTICE ───  (12px uppercase gray section label)
      Sessions (Calendar icon)    → /sessions
      Leaderboard (Trophy icon)   → /leaderboard (stub)
    Active item: bg-blue-50 text-blue-600 rounded-lg
    Slide animation: translateX(-100%) → 0, 200ms ease-in-out
    ```

12. `frontend/src/components/layout/DashboardLayout.tsx`:
    ```tsx
    <div className="min-h-screen bg-page font-sans">
      <TopNav onMenuClick={() => setDrawerOpen(true)} />
      <SideDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      <main className="px-8 py-6 flex gap-6">
        <div className="flex-1 min-w-0">{children}</div>  {/* main content */}
        <aside className="w-[280px] flex-shrink-0">{sidebar}</aside>
      </main>
    </div>
    ```

---

### Day 2 — Dashboard Page

**Backend**

1. `backend/app/models/course.py`:
   ```python
   class ClassSession(Base):
       id, course_id, host_id, title, description, scheduled_at, duration_mins
       zoom_meeting_id, status (SCHEDULED|LIVE|ENDED), created_at, updated_at
   ```

2. `backend/app/api/sessions.py`:
   - `GET /api/sessions` — list sessions for enrolled courses, with `?status=upcoming|past`
   - `GET /api/sessions/:id` — session detail
   - `GET /api/sessions/this-week` — sessions from today to +6 days (for timetable)

3. `backend/app/api/courses.py`:
   - `GET /api/courses` — enrolled courses with progress stats (attendance %, problems solved)
   - `GET /api/courses/:id`
   - `POST /api/courses/:id/enroll` (instructor or admin only)

4. Alembic migration for courses, class_sessions, enrollments

**Frontend**

5. `frontend/src/pages/DashboardPage.tsx`:
   Layout uses `DashboardLayout` with `<DashboardSidebar>` in the sidebar slot.

6. `frontend/src/components/dashboard/TimetableSection.tsx`:
   ```
   Section heading: "Time Table" (20px, semibold)
   DateTabStrip: 7 tabs for today + next 6 days
     Each tab: day abbrev (Mon) + date (18) — 14px
     Active: text-blue-600 border-b-2 border-blue-600
     Inactive: text-muted
   ClassCard per session that day:
     width: ~190px, border-radius: 8px
     Left: teacher avatar placeholder (blue circle)
     Right: class name (bold), "Live Meeting" gray label, time range, "View Details" blue link
   No classes that day → empty state: "No classes scheduled"
   ```

7. `frontend/src/components/dashboard/ContinueWatchingSection.tsx`:
   ```
   Section heading: "Continue Watching" + [→] blue circle arrow button (right-aligned)
   Horizontal scroll row: gap-4, overflow-x-auto, no scrollbar visible
   VideoCard component (see below)
   ```

8. `frontend/src/components/dashboard/VideoCard.tsx`:
   ```
   width: 250px, border-radius: 8px, overflow-hidden, bg-white, shadow-card
   Thumbnail (140px tall):
     bg: topic color (blue/green/pink from getTopicColor())
     Title (white, bold, 14px, top-left, p-3)
     Date (white, 12px, top-left below title)
     Play button: white circle 40px centered, play icon inside
     Progress bar: 4px tall green bar at bottom, width = watchPercent%
   Body (p-3):
     Course name (14px, semibold, text-primary)
     Row: "Attendance: {n}" text-muted | "Resume" blue link (right)
   ```
   Data from: `/api/sessions?status=past&with_progress=true`

9. `frontend/src/components/dashboard/DashboardSidebar.tsx` (right column):

   a. `YearRevisitedBanner`:
      ```
      bg: linear-gradient(135deg, #1E3A8A, #312E81)
      border-radius: 8px, p-4, text-white
      "2025 Revisited — Check out your year at nodeLive >"
      ```

   b. `PerformanceWidget`:
      ```
      bg-white, rounded-card, p-4, shadow-card
      "Performance" header (16px, semibold)
      Two ProgressBar rows:
        Attendance: label + percent value + green bar
        Problems Solved: label + fraction + green bar
      Bar: h-1.5 bg-gray-100 rounded, fill bg-green-500
      ```

   c. `NoticeBoardWidget`:
      ```
      bg-white, rounded-card, p-4, shadow-card
      "Notice Board" header
      List of notices: FileText icon + title + [NEW] green badge
      ```

   All data via React Query → `/api/dashboard/widgets`

10. `frontend/src/hooks/useDashboard.ts` — TanStack Query hooks for all dashboard API calls

---

### Day 3 — Session Detail Page + Polish

**Backend**

1. `GET /api/sessions/:id/similar` — sessions from same course, sorted by date, limit 5
2. `GET /api/dashboard/widgets` — combined endpoint: attendance%, problems, notices (avoids 3 fetches)
3. `GET /api/sessions/this-week` — sessions grouped by date for timetable (backend aggregation)

**Frontend**

4. `frontend/src/pages/SessionDetailPage.tsx` — `/session/:id`
   ```
   Same TopNav (no sidebar on this page — full width)
   Breadcrumb header:
     ← {sessionTitle} ▼   [Mandatory badge]   🔔  📹{attendance}%
   Tab bar: Session | Assignment | Feedback
   ```

5. `frontend/src/components/session/UpcomingSessionHero.tsx`:
   ```
   border-radius: 12px
   bg: linear-gradient(to bottom right, #DBEAFE, #EFF6FF)
   height: ~260px, p-8, display: flex align-center gap-8
   Left: SVG illustration (simple teacher at whiteboard — use a free SVG or placeholder)
   Right:
     "Upcoming Session" yellow pill badge (#FEF9C3 bg, #854D0E text)
     Session title (bold, 20px)
     📅 date + 🕐 "Starts at HH:MM" row
     [Join Session] button (red #DC2626, rounded-btn, px-6 py-2)
       → onClick → navigate to /live/:sessionId
   ```

6. `frontend/src/components/session/SimilarSessionsRow.tsx`:
   ```
   "Sessions similar to this:" heading
   Same horizontal scroll VideoCard row as ContinueWatching
   Data from /api/sessions/:id/similar
   ```

7. `frontend/src/components/session/SessionTabBar.tsx`:
   ```
   height: 48px, border-bottom: 1px solid #E2E8F0, flex gap-6, px-6
   Tabs: Session | Assignment 0/0 | Feedback 🔒
   Active: text-blue-600 border-b-2 border-blue-600
   Feedback locked until session status = ENDED
   ```

8. **Polish pass** — test all pages, fix:
   - Font loading (Source Sans Pro via Google Fonts in index.html + Tailwind config)
   - Loading skeletons (shadcn Skeleton component) for all React Query fetches
   - Error boundaries per page
   - Empty states (no classes today, no sessions, etc.)
   - Auth redirect guard on dashboard/session routes

---

## Backend File Structure (Branch A owns)

```
backend/
├── app/
│   ├── api/
│   │   ├── auth.py         ← NEW (signup, login, logout, /me)
│   │   ├── courses.py      ← NEW (list, detail, enroll)
│   │   ├── sessions.py     ← NEW (list, detail, this-week, similar)
│   │   └── dashboard.py    ← NEW (widgets combined endpoint)
│   ├── models/
│   │   ├── base.py         ← SHARED (from foundation)
│   │   ├── user.py         ← NEW
│   │   └── course.py       ← NEW (Course, ClassSession, Enrollment)
│   ├── schemas/
│   │   ├── auth.py         ← NEW (SignupIn, LoginIn, UserOut)
│   │   ├── course.py       ← NEW
│   │   └── session.py      ← NEW
│   └── auth/
│       ├── tokens.py       ← NEW
│       └── deps.py         ← NEW (get_current_user, require_role)
└── alembic/versions/
    └── 001_users_courses.py  ← NEW
```

---

## Frontend File Structure (Branch A owns)

```
frontend/src/
├── pages/
│   ├── LoginPage.tsx        ← NEW
│   ├── SignupPage.tsx       ← NEW
│   └── DashboardPage.tsx    ← NEW
│   └── SessionDetailPage.tsx ← NEW
├── components/
│   ├── layout/
│   │   ├── TopNav.tsx       ← NEW
│   │   ├── SideDrawer.tsx   ← NEW
│   │   └── DashboardLayout.tsx ← NEW
│   ├── dashboard/
│   │   ├── TimetableSection.tsx    ← NEW
│   │   ├── DateTabStrip.tsx        ← NEW
│   │   ├── ClassCard.tsx           ← NEW
│   │   ├── VideoCard.tsx           ← NEW
│   │   ├── ContinueWatchingSection.tsx ← NEW
│   │   └── DashboardSidebar.tsx    ← NEW
│   │       ├── YearRevisitedBanner.tsx
│   │       ├── PerformanceWidget.tsx
│   │       └── NoticeBoardWidget.tsx
│   └── session/
│       ├── UpcomingSessionHero.tsx  ← NEW
│       ├── SimilarSessionsRow.tsx   ← NEW
│       └── SessionTabBar.tsx        ← NEW
├── hooks/
│   ├── useAuth.ts           ← NEW (auth store + queries)
│   └── useDashboard.ts      ← NEW (sessions + widget queries)
└── stores/
    └── authStore.ts         ← NEW (Zustand)
```

---

## API Contract (Dev B needs to know — shared interface)

These are the endpoints Dev B (live meeting) depends on from Branch A:

| Endpoint | Returns | Notes |
|----------|---------|-------|
| `GET /api/auth/me` | `User` | Used by live meeting to know current user |
| `GET /api/sessions/:id` | `ClassSession` | Live class reads title, host, zoomMeetingId |
| `PATCH /api/sessions/:id` | `ClassSession` | Dev B calls this to set `status = LIVE/ENDED` |

JSON shapes:
```ts
interface User {
  id: string
  email: string
  displayName: string
  role: 'STUDENT' | 'INSTRUCTOR' | 'ADMIN'
  avatarUrl: string | null
  coins: number
}

interface ClassSession {
  id: string
  courseId: string
  hostId: string
  title: string
  scheduledAt: string  // ISO 8601
  durationMins: number
  zoomMeetingId: string | null
  status: 'SCHEDULED' | 'LIVE' | 'ENDED' | 'CANCELLED'
}
```

---

## Seed Data (for local dev)

Create `backend/scripts/seed.py`:
```python
# Creates: 2 courses, 5 sessions (2 upcoming, 3 past), 3 users (1 instructor, 2 students)
# Run: python -m scripts.seed
```

Seed data lets Dev B test live meeting without needing real Zoom meetings initially.

---

## Component Pixel Specs (exact measurements from screenshots)

### TopNav
```css
height: 64px;
background: #FFFFFF;
border-bottom: 1px solid #E2E8F0;
padding: 0 32px;
display: flex; align-items: center; justify-content: space-between;
position: sticky; top: 0; z-index: 50;

.logo { display: flex; align-items: center; gap: 10px; }
.logo-text { font-size: 18px; font-weight: 700; color: #111827; }
.hamburger { cursor: pointer; padding: 8px; border-radius: 6px; }
.hamburger:hover { background: #F3F4F6; }

.right-group { display: flex; align-items: center; gap: 16px; }
.coin-counter { display: flex; align-items: center; gap: 6px; 
  border: 1px solid #D97706; border-radius: 20px; padding: 4px 12px;
  color: #D97706; font-size: 14px; font-weight: 600; }
.bell-btn { padding: 8px; border-radius: 50%; cursor: pointer; }
.user-avatar { width: 32px; height: 32px; border-radius: 50%; 
  background: #2563EB; color: white; font-size: 13px; font-weight: 600;
  display: flex; align-items: center; justify-content: center; }
```

### ClassCard
```css
width: 190px; padding: 12px 16px;
background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px;
display: flex; gap: 12px; align-items: flex-start;

.teacher-avatar { width: 40px; height: 40px; border-radius: 50%; 
  background: #DBEAFE; flex-shrink: 0; }
.class-name { font-size: 14px; font-weight: 600; color: #111827; }
.class-type { font-size: 12px; color: #6B7280; margin-top: 2px; }
.class-time { font-size: 12px; color: #6B7280; }
.view-link { font-size: 13px; color: #2563EB; font-weight: 500; margin-top: 4px; }
```

### ProgressBar
```css
.progress-track { width: 100%; height: 6px; background: #E2E8F0; border-radius: 4px; }
.progress-fill { height: 100%; background: #22C55E; border-radius: 4px; 
  transition: width 300ms ease; }
```

---

## Checklist

### Backend
- [x] User model + migration — `app/models/user.py`, migration `2c3e7d95e6bc_users_courses_class_sessions.py`
- [x] Course + ClassSession + Enrollment models + migration — `app/models/course.py` (all three classes); enrollments migration `d94ea5abad38_enrollments.py`
- [x] Auth routes (signup, login, logout, /me) — `app/api/auth.py` (Argon2id, JWT cookie)
- [x] JWT token creation + validation dependency — `app/auth/tokens.py` (`create_access_token`/`decode_token`), `app/auth/deps.py` (`get_current_user` + role guards)
- [x] `/api/sessions` list + detail + this-week + similar — `app/api/sessions.py` (all present, plus `POST` create + `PATCH`)
- [x] `/api/courses` list — `app/api/courses.py` (read-only; **note:** `POST /api/courses/:id/enroll` was NOT built — enroll lives under the admin API instead)
- [x] `/api/dashboard/widgets` combined — **shipped as `GET /api/dashboard/stats`** (`app/api/dashboard.py`), consumed by `useDashboard.ts`
- [x] Seed data script — `backend/scripts/seed.py`
- [x] pytest tests for auth routes — `backend/tests/test_auth.py` (plus `test_sessions.py`, `test_dashboard*.py`)

### Frontend
- [~] Google Fonts: Source Sans Pro in index.html — **font shipped as self-hosted Inter** (`@fontsource-variable/inter`, imported in `main.tsx`; see `styles/globals.css`), not Source Sans Pro via Google Fonts
- [x] Tailwind config with all design tokens — design tokens in `frontend/src/styles/globals.css` (Tailwind 4 CSS-first config)
- [x] shadcn/ui init + Button, Card, Badge, Skeleton, Dialog, Dropdown — `components/ui/` has `button`, `card`, `badge`, `skeleton`, `dropdown-menu`, `ConfirmDialog` (Dialog variant)
- [x] LoginPage + SignupPage — `pages/LoginPage.tsx`, `pages/SignupPage.tsx` (shared `components/auth/AuthShell.tsx`)
- [x] Auth hook (Zustand + React Query) — `hooks/useAuth.ts`
- [x] React Router setup with auth guard — `router.tsx` + `components/auth/guards.tsx` (`ProtectedRoute`/`PublicOnlyRoute`/`AdminRoute`)
- [x] TopNav component — `components/layout/TopNav.tsx`
- [x] SideDrawer component (with animation) — `components/layout/SideDrawer.tsx`
- [x] DashboardLayout (main content + right sidebar slot) — `components/layout/DashboardLayout.tsx`
- [x] DashboardPage with all sections — `pages/DashboardPage.tsx`
- [x] VideoCard component — `components/dashboard/VideoCard.tsx`
- [x] ContinueWatchingSection (horizontal scroll) — `components/dashboard/ContinueWatchingSection.tsx`
- [x] TimetableSection + DateTabStrip + ClassCard — `components/dashboard/{TimetableSection,DateTabStrip,ClassCard}.tsx`
- [x] DashboardSidebar (PerformanceWidget + NoticeBoardWidget) — `components/dashboard/DashboardSidebar.tsx`
- [x] SessionDetailPage — `pages/SessionDetailPage.tsx`
- [x] UpcomingSessionHero (with "Join Session" → /live/:id nav) — `components/session/UpcomingSessionHero.tsx` (navigates to `/live/:id`; shows "Watch recording" when ended)
- [x] SessionTabBar — `components/session/SessionTabBar.tsx` (tabs: Session | Assignment | Notes | Feedback, + Analytics)
- [x] SimilarSessionsRow — `components/session/SimilarSessionsRow.tsx`
- [x] Loading skeletons on all data fetches — Skeleton used in dashboard sections, SessionDetail, Sessions, Leaderboard pages
- [x] Empty states — e.g. `TimetableSection.tsx` "No classes scheduled for this day."
