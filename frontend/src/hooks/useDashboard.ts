import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { ClassSession, Course } from '@/types'

// Session lists must reflect a newly scheduled/cancelled class without a manual
// reload — e.g. an instructor schedules while students sit on their dashboard.
// The global QueryClient disables focus-refetch and has no polling, so opt these
// lists in explicitly: poll every 20s and refetch when the tab regains focus.
const LIVE_LIST = { refetchInterval: 20_000, refetchOnWindowFocus: true } as const

export function useThisWeek() {
  return useQuery({
    queryKey: ['sessions', 'this-week'],
    queryFn: () => api.get<ClassSession[]>('/api/sessions/this-week'),
    ...LIVE_LIST,
  })
}

export function usePastSessions() {
  return useQuery({
    queryKey: ['sessions', 'past'],
    queryFn: () => api.get<ClassSession[]>('/api/sessions?status=past'),
    ...LIVE_LIST,
  })
}

export function useUpcomingSessions() {
  return useQuery({
    queryKey: ['sessions', 'upcoming'],
    queryFn: () => api.get<ClassSession[]>('/api/sessions?status=upcoming'),
    ...LIVE_LIST,
  })
}

export function useCourses() {
  return useQuery({
    queryKey: ['courses'],
    queryFn: () => api.get<Course[]>('/api/courses'),
  })
}

export interface DashboardStats {
  assignmentsGraded: number
  assignmentsTotal: number
  coursesEnrolled: number
}

export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: () => api.get<DashboardStats>('/api/dashboard/stats'),
  })
}

export interface AssignmentProgressItem {
  id: string
  title: string
  maxPoints: number
  dueAt: string | null
  status: 'SUBMITTED' | 'GRADED' | null
  grade: number | null
  feedback: string | null
  submittedAt: string | null
}

export interface SessionProgressItem {
  id: string
  title: string
  sessionStatus: string
  scheduledAt: string
  watchPercent: number | null
}

export interface CourseProgressItem {
  id: string
  title: string
  assignments: AssignmentProgressItem[]
  sessions: SessionProgressItem[]
}

export interface MyProgress {
  courses: CourseProgressItem[]
  assignmentsTotal: number
  assignmentsSubmitted: number
  assignmentsGraded: number
  avgGrade: number | null
}

export function useMyProgress() {
  return useQuery({
    queryKey: ['me', 'progress'],
    queryFn: () => api.get<MyProgress>('/api/me/progress'),
  })
}
