/**
 * Fetches the `/live/state` snapshot and hydrates the live store on join and
 * on every reconnect-driven refetch, so client state survives network hiccups.
 */

import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import { api } from '@/lib/api'
import { useLiveClassStore } from '@/stores/liveClassStore'
import type { LiveState } from '@/types'

export function useLiveState(sessionId: string) {
  const hydrate = useLiveClassStore((s) => s.hydrate)
  const query = useQuery({
    queryKey: ['live-state', sessionId],
    queryFn: () => api.get<LiveState>(`/api/sessions/${sessionId}/live/state`),
    enabled: Boolean(sessionId),
  })

  useEffect(() => {
    if (query.data) hydrate(query.data)
  }, [query.data, hydrate])

  return query
}
