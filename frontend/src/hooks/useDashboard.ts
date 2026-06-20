import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { ClassSession, Course } from '@/types'

export function useThisWeek() {
  return useQuery({
    queryKey: ['sessions', 'this-week'],
    queryFn: () => api.get<ClassSession[]>('/api/sessions/this-week'),
  })
}

export function usePastSessions() {
  return useQuery({
    queryKey: ['sessions', 'past'],
    queryFn: () => api.get<ClassSession[]>('/api/sessions?status=past'),
  })
}

export function useUpcomingSessions() {
  return useQuery({
    queryKey: ['sessions', 'upcoming'],
    queryFn: () => api.get<ClassSession[]>('/api/sessions?status=upcoming'),
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
