import { Play } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useQuery } from '@tanstack/react-query'
import { ApiError, api } from '@/lib/api'
import { getTopicColor } from '@/lib/topicColor'
import type { ClassSession } from '@/types'

function useWatchStatus(sessionId: string) {
  return useQuery({
    queryKey: ['recording', sessionId, 'watch-status'],
    queryFn: () =>
      api.get<{ available: boolean; percentComplete: number }>(
        `/api/sessions/${sessionId}/recording/watch-status`,
      ),
    retry: (count, err) =>
      !(err instanceof ApiError && err.status === 401) && count < 1,
    staleTime: 60_000,
  })
}

export function VideoCard({ session }: { session: ClassSession }) {
  const color = getTopicColor(session.title)
  const date = new Date(session.scheduledAt).toLocaleDateString('en-US', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
  const { data: ws } = useWatchStatus(session.id)
  const pct = ws?.available ? Math.round(ws.percentComplete) : null

  return (
    <Link
      to={`/session/${session.id}/recording`}
      className="group block w-[250px] shrink-0 overflow-hidden rounded-card border border-border bg-card shadow-card transition-shadow hover:shadow-elevated"
    >
      <div
        className="relative flex h-[130px] flex-col justify-between p-3 text-white"
        style={{ backgroundColor: color }}
      >
        <div>
          <p className="line-clamp-2 text-sm font-semibold">{session.title}</p>
          <p className="mt-0.5 text-xs text-white/80">{date}</p>
        </div>
        <span className="absolute left-1/2 top-1/2 flex h-10 w-10 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-text-primary transition-transform group-hover:scale-105">
          <Play className="h-4 w-4 fill-current" />
        </span>
      </div>
      <div className="p-3">
        <div className="flex items-center justify-between">
          <p className="truncate text-sm font-semibold text-text-primary">
            Lecture recording
          </p>
          <span className="text-sm font-medium text-text-link">
            {pct !== null && pct > 0 ? 'Resume' : 'Watch'}
          </span>
        </div>
        {pct !== null && (
          <div className="mt-2">
            <div className="h-1 w-full overflow-hidden rounded-full bg-border-muted">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
            <p className="mt-0.5 text-right text-xs text-text-muted">{pct}%</p>
          </div>
        )}
      </div>
    </Link>
  )
}
