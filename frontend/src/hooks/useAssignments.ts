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

export interface UploadUrlResult {
  uploadUrl: string
  fileKey: string
}

export function useUploadUrl(assignmentId: string) {
  return useMutation({
    mutationFn: ({
      filename,
      contentType,
    }: {
      filename: string
      contentType: string
    }) =>
      api.post<UploadUrlResult>(
        `/api/assignments/${assignmentId}/upload-url?filename=${encodeURIComponent(filename)}&contentType=${encodeURIComponent(contentType)}`,
      ),
  })
}

/**
 * Fetch a short-lived presigned GET URL for a file submission and open it.
 * Lets the student re-download their own file and the instructor download it
 * to grade. Toasts if storage is unconfigured (501) or the file is missing.
 */
export function useDownloadSubmission() {
  return useMutation({
    mutationFn: (submissionId: string) =>
      api.get<{ url: string }>(`/api/submissions/${submissionId}/file-url`),
    onSuccess: ({ url }) => window.open(url, '_blank', 'noopener,noreferrer'),
    onError: () =>
      toast({ variant: 'error', title: 'Could not open the file.' }),
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
