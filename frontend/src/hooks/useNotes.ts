import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import type { LectureNote, NoteKind } from '@/types'

export function useNotes(sessionId: string) {
  return useQuery({
    queryKey: ['notes', sessionId],
    queryFn: () => api.get<LectureNote[]>(`/api/sessions/${sessionId}/notes`),
    enabled: Boolean(sessionId),
  })
}

export function useCreateNote(sessionId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: { title: string; url: string; kind: NoteKind }) =>
      api.post<LectureNote>(`/api/sessions/${sessionId}/notes`, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notes', sessionId] })
      toast({ variant: 'success', title: 'Material added' })
    },
  })
}
