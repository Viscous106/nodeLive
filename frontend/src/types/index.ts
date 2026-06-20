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

// --- Live-meeting (Dev B) — mirror backend/app/schemas/live.py --------------

/** POST /api/sessions/:id/join → Zoom SDK credentials. */
export interface ZoomJoin {
  signature: string
  sdkKey: string
  zoomMeetingId: string
}

export interface CueCard {
  id: string
  content: string
  displayOrder: number
  shownAt: string | null
}

export type PollStatus = 'OPEN' | 'CLOSED'

export interface Poll {
  id: string
  question: string
  options: string[]
  status: PollStatus
}

export interface PollOptionResult {
  optionIndex: number
  count: number
  pct: number
}

export interface PollResults {
  pollId: string
  status: PollStatus
  results: PollOptionResult[]
}

export type QuizStatus = 'DRAFT' | 'LIVE' | 'ENDED'

export interface Quiz {
  id: string
  title: string
  timeLimitSecs: number
  status: QuizStatus
}

/** A live quiz question as broadcast by the server timer (no correct answer). */
export interface ActiveQuestion {
  quizId: string
  questionId: string
  index: number
  text: string
  options: string[]
  timeLeft: number
}

export interface QuizScore {
  questionId: string
  correct: boolean
  points: number
}

export interface Notice {
  id: string
  content: string
  priority: string
  createdAt: string
  expiresAt: string | null
}

export interface Bookmark {
  id: string
  timestampMs: number
  label: string | null
  createdAt: string
}

export interface RankedUser {
  userId: string
  displayName: string
  points: number
}

export interface RaisedHand {
  userId: string
  name?: string | null
}

/** GET /api/sessions/:id/live/state — reconnect snapshot. */
export interface LiveState {
  currentCueCard: CueCard | null
  activePoll: Poll | null
  activeQuiz: Quiz | null
  pinnedMessage: string | null
  recentNotices: Notice[]
  userBookmarks: Bookmark[]
  myQuizScore: number
  leaderboard: RankedUser[]
}
