import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { ClassSession } from '@/types'

export function useSession(id: string) {
  return useQuery({
    queryKey: ['session', id],
    queryFn: () => api.get<ClassSession>(`/api/sessions/${id}`),
    enabled: Boolean(id),
    // While the class hasn't started, poll so a waiting student auto-enters the
    // moment the host starts it (status → LIVE); stop polling once it's live.
    refetchInterval: (query) =>
      query.state.data?.status === 'LIVE' ? false : 5000,
  })
}

export function useSimilarSessions(id: string) {
  return useQuery({
    queryKey: ['session', id, 'similar'],
    queryFn: () => api.get<ClassSession[]>(`/api/sessions/${id}/similar`),
    enabled: Boolean(id),
  })
}
