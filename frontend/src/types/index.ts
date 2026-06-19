/**
 * Shared API contract types.
 *
 * The single source of truth for shapes that cross the Dev A (dashboard) /
 * Dev B (live-meeting) boundary. Keep these in sync with the FastAPI Pydantic
 * schemas. Change here = coordinate with both devs.
 */

// Enum values are UPPERCASE to match the backend Pydantic schemas exactly
// (UserRole / SessionStatus). Source of truth: backend/app/schemas.
export type UserRole = 'STUDENT' | 'INSTRUCTOR' | 'ADMIN'

export interface User {
  id: string
  email: string
  displayName: string
  role: UserRole
  avatarUrl: string | null
  coins: number
}

export type SessionStatus = 'SCHEDULED' | 'LIVE' | 'ENDED' | 'CANCELLED'

export interface Course {
  id: string
  title: string
}

export interface ClassSession {
  id: string
  courseId: string
  hostId: string
  title: string
  description: string | null
  scheduledAt: string // ISO 8601
  durationMins: number
  status: SessionStatus
  zoomMeetingId: string | null
}

export interface Assignment {
  id: string
  courseId: string
  sessionId: string | null
  title: string
  description: string | null
  dueAt: string | null // ISO 8601
  maxPoints: number
  unlockedAt: string | null
}

export type SubmissionStatus = 'SUBMITTED' | 'GRADED'

export interface Submission {
  id: string
  assignmentId: string
  userId: string
  content: string
  status: SubmissionStatus
  grade: number | null
  feedback: string | null
}

/** Credentials returned by GET /api/sessions/:id/zoom-token (Dev B owns). */
export interface ZoomJoinToken {
  sdkKey: string
  signature: string
  sessionName: string
  userName: string
  zak?: string
}

/** Standard error body shape from the API. */
export interface ApiErrorBody {
  detail: string | { msg: string; loc: (string | number)[] }[]
}
