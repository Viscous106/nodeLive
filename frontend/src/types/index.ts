/**
 * Shared API contract types.
 *
 * The single source of truth for shapes that cross the Dev A (dashboard) /
 * Dev B (live-meeting) boundary. Keep these in sync with the FastAPI Pydantic
 * schemas. Change here = coordinate with both devs.
 */

export type UserRole = 'student' | 'instructor' | 'admin'

export interface User {
  id: string
  email: string
  displayName: string
  role: UserRole
  avatarUrl: string | null
  coins: number
  createdAt: string // ISO 8601
}

export type SessionStatus = 'scheduled' | 'live' | 'ended'

export interface Course {
  id: string
  title: string
  description: string | null
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
