import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import type {
  ClassSession,
  Course,
  Enrollment,
  Invitation,
  InvitePreview,
  Member,
  SessionStatus,
  UserRole,
} from '@/types'

const MEMBERS_KEY = ['admin', 'members'] as const
const INVITES_KEY = ['admin', 'invitations'] as const

export function useMembers() {
  return useQuery({
    queryKey: MEMBERS_KEY,
    queryFn: () => api.get<Member[]>('/api/admin/members'),
  })
}

export function useSetRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UserRole }) =>
      api.patch<Member>(`/api/admin/members/${userId}/role`, { role }),
    onSuccess: (m) => {
      qc.invalidateQueries({ queryKey: MEMBERS_KEY })
      toast({ variant: 'success', title: `${m.displayName} is now ${m.role}` })
    },
    onError: (e) =>
      toast({
        variant: 'error',
        title:
          e instanceof ApiError && e.status === 409
            ? 'An org must keep at least one admin.'
            : 'Could not update the role.',
      }),
  })
}

export function useInvitations() {
  return useQuery({
    queryKey: INVITES_KEY,
    queryFn: () => api.get<Invitation[]>('/api/admin/invitations'),
  })
}

export function useCreateInvitation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: { email: string; role: UserRole }) =>
      api.post<Invitation>('/api/admin/invitations', input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: INVITES_KEY })
      toast({ variant: 'success', title: 'Invitation created' })
    },
    onError: (e) =>
      toast({
        variant: 'error',
        title:
          e instanceof ApiError && e.status === 409
            ? 'That email already belongs to a member.'
            : 'Could not create the invitation.',
      }),
  })
}

export function useRevokeInvitation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete<null>(`/api/admin/invitations/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: INVITES_KEY }),
  })
}

/** Public invite preview (signup screen) — no auth. */
export function useInvitePreview(token: string | null) {
  return useQuery({
    queryKey: ['invite', token],
    queryFn: () => api.get<InvitePreview>(`/api/invitations/${token}`),
    enabled: Boolean(token),
    retry: false,
    staleTime: Infinity,
  })
}

// --- Sessions (schedule & manage) -------------------------------------------

const SESSIONS_KEY = ['admin', 'sessions'] as const

export interface SessionInput {
  courseId: string
  hostId?: string | null
  title: string
  description?: string | null
  scheduledAt: string // ISO 8601
  durationMins: number
  zoomMeetingId?: string | null
}

export function useAdminSessions(status?: SessionStatus | 'ALL') {
  const filter = status && status !== 'ALL' ? `?status=${status}` : ''
  return useQuery({
    queryKey: [...SESSIONS_KEY, status ?? 'ALL'],
    queryFn: () => api.get<ClassSession[]>(`/api/admin/sessions${filter}`),
  })
}

export function useAdminCourses() {
  return useQuery({
    queryKey: ['admin', 'courses'],
    queryFn: () => api.get<Course[]>('/api/admin/courses'),
  })
}

export function useCreateCourse() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (title: string) =>
      api.post<Course>('/api/admin/courses', { title }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'courses'] })
      toast({ variant: 'success', title: 'Course created' })
    },
    onError: () =>
      toast({ variant: 'error', title: 'Could not create the course.' }),
  })
}

export function useCreateSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: SessionInput) =>
      api.post<ClassSession>('/api/sessions', input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SESSIONS_KEY })
      toast({ variant: 'success', title: 'Session scheduled' })
    },
    onError: () =>
      toast({ variant: 'error', title: 'Could not schedule the session.' }),
  })
}

export function useUpdateSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...patch }: { id: string } & Partial<SessionInput>) =>
      api.patch<ClassSession>(`/api/sessions/${id}`, patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SESSIONS_KEY })
      toast({ variant: 'success', title: 'Session updated' })
    },
    onError: () =>
      toast({ variant: 'error', title: 'Could not update the session.' }),
  })
}

export function useCancelSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post<ClassSession>(`/api/admin/sessions/${id}/cancel`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SESSIONS_KEY })
      toast({ variant: 'success', title: 'Session cancelled' })
    },
    onError: () =>
      toast({ variant: 'error', title: 'Could not cancel the session.' }),
  })
}

// --- instructor list (for host picker) ---------------------------------------

export function useInstructors() {
  return useQuery({
    queryKey: ['admin', 'instructors'],
    queryFn: () => api.get<Member[]>('/api/admin/instructors'),
  })
}

// --- enrollment management ---------------------------------------------------

const ENROLLMENTS_KEY = ['admin', 'enrollments'] as const

export function useEnrollments(courseId?: string) {
  const qs = courseId ? `?courseId=${courseId}` : ''
  return useQuery({
    queryKey: [...ENROLLMENTS_KEY, courseId ?? 'all'],
    queryFn: () => api.get<Enrollment[]>(`/api/admin/enrollments${qs}`),
  })
}

export function useCreateEnrollment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: { userId: string; courseId: string }) =>
      api.post<Enrollment>('/api/admin/enrollments', input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ENROLLMENTS_KEY })
      toast({ variant: 'success', title: 'User enrolled' })
    },
    onError: (e) =>
      toast({
        variant: 'error',
        title:
          e instanceof ApiError && e.status === 409
            ? 'User is already enrolled in this course.'
            : 'Could not enroll user.',
      }),
  })
}

export function useDeleteEnrollment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.delete<null>(`/api/admin/enrollments/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ENROLLMENTS_KEY })
      toast({ variant: 'success', title: 'Enrollment removed' })
    },
    onError: () =>
      toast({ variant: 'error', title: 'Could not remove enrollment.' }),
  })
}
