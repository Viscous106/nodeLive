import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { ClassSession } from '@/types'

export function useSession(id: string) {
  return useQuery({
    queryKey: ['session', id],
    queryFn: () => api.get<ClassSession>(`/api/sessions/${id}`),
    enabled: Boolean(id),
  })
}

export function useSimilarSessions(id: string) {
  return useQuery({
    queryKey: ['session', id, 'similar'],
    queryFn: () => api.get<ClassSession[]>(`/api/sessions/${id}/similar`),
    enabled: Boolean(id),
  })
}
