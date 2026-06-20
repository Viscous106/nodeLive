import { useMutation, useQuery } from '@tanstack/react-query'

import { api, ApiError } from '@/lib/api'

export interface RecordingUrl {
  url: string
  expiresInSecs: number
}
export interface Progress {
  lastPositionSecs: number
  percentComplete: number
  segments: number[][]
}
export interface WatchStatus {
  available: boolean
  percentComplete: number
  lastPositionSecs: number
  durationSecs: number | null
}
export interface HeartbeatBody {
  playedFrom: number
  playedTo: number
  duration: number
}

// The backend serializes snake_case; map to camelCase at the edge.
interface ProgressWire {
  last_position_secs: number
  percent_complete: number
  segments: number[][] | null
}

function camelProgress(p: ProgressWire): Progress {
  return {
    lastPositionSecs: p.last_position_secs,
    percentComplete: p.percent_complete,
    segments: p.segments ?? [],
  }
}

export function useRecordingUrl(sessionId: string) {
  return useQuery({
    queryKey: ['recording', sessionId, 'url'],
    queryFn: async () => {
      const r = await api.get<{ url: string; expires_in_secs: number }>(
        `/api/sessions/${sessionId}/recording/url`,
      )
      return { url: r.url, expiresInSecs: r.expires_in_secs } as RecordingUrl
    },
    retry: (count, err) =>
      // don't retry the expected "not available / not configured" states
      !(err instanceof ApiError && [404, 501].includes(err.status)) && count < 2,
  })
}

export function useRecordingProgress(sessionId: string) {
  return useQuery({
    queryKey: ['recording', sessionId, 'progress'],
    queryFn: async () =>
      camelProgress(
        await api.get<ProgressWire>(`/api/sessions/${sessionId}/recording/progress`),
      ),
  })
}

export function useHeartbeat(sessionId: string) {
  return useMutation({
    mutationFn: async (b: HeartbeatBody) =>
      camelProgress(
        await api.post<ProgressWire>(`/api/sessions/${sessionId}/recording/heartbeat`, {
          played_from: b.playedFrom,
          played_to: b.playedTo,
          duration: b.duration,
        }),
      ),
  })
}
