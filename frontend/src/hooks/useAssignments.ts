import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, ApiError } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import type { Assignment, Submission } from '@/types'

export function useAssignments(sessionId: string) {
  return useQuery({
    queryKey: ['assignments', 'session', sessionId],
    queryFn: () => api.get<Assignment[]>(`/api/assignments?sessionId=${sessionId}`),
    enabled: Boolean(sessionId),
  })
}

export function useMySubmission(assignmentId: string) {
  return useQuery({
    queryKey: ['submission', 'mine', assignmentId],
    queryFn: async () => {
      try {
        return await api.get<Submission>(
          `/api/assignments/${assignmentId}/my-submission`,
        )
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null
        throw e
      }
    },
  })
}

export function useSubmit(assignmentId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (content: string) =>
      api.post<Submission>(`/api/assignments/${assignmentId}/submissions`, {
        content,
      }),
    onSuccess: (sub) => {
      qc.setQueryData(['submission', 'mine', assignmentId], sub)
      toast({ variant: 'success', title: 'Submitted' })
    },
  })
}

export interface CreateAssignmentInput {
  courseId: string
  sessionId: string
  title: string
  description?: string
  maxPoints?: number
}

export function useCreateAssignment(sessionId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateAssignmentInput) =>
      api.post<Assignment>('/api/assignments', input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assignments', 'session', sessionId] })
      toast({ variant: 'success', title: 'Assignment created' })
    },
  })
}

export function useSubmissions(assignmentId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['submissions', assignmentId],
    queryFn: () =>
      api.get<Submission[]>(`/api/assignments/${assignmentId}/submissions`),
    enabled,
  })
}

export function useGrade(assignmentId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: { id: string; grade: number; feedback?: string }) =>
      api.patch<Submission>(`/api/submissions/${input.id}`, {
        grade: input.grade,
        feedback: input.feedback,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['submissions', assignmentId] })
      toast({ variant: 'success', title: 'Grade saved' })
    },
  })
}
