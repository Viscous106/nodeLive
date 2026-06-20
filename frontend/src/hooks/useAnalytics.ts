import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { SessionAnalytics } from '@/types'

export function useSessionAnalytics(sessionId: string) {
  return useQuery({
    queryKey: ['analytics', sessionId],
    queryFn: () =>
      api.get<SessionAnalytics>(`/api/sessions/${sessionId}/analytics`),
    enabled: Boolean(sessionId),
  })
}
