import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { RankedUser } from '@/types'

export function useLeaderboard() {
  return useQuery({
    queryKey: ['leaderboard'],
    queryFn: () => api.get<RankedUser[]>('/api/leaderboard'),
  })
}
