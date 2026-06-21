import { Link } from 'react-router-dom'

import type { ClassSession } from '@/types'

function timeRange(iso: string, mins: number): string {
  const start = new Date(iso)
  const end = new Date(start.getTime() + mins * 60_000)
  const fmt = (d: Date) =>
    d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  return `${fmt(start)} – ${fmt(end)}`
}

export function ClassCard({ session }: { session: ClassSession }) {
  const isLive = session.status === 'LIVE'
  return (
    <div className="flex items-start gap-3 rounded-card border border-border bg-card p-4 transition-all hover:border-primary/40 hover:shadow-card">
      <span
        className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary"
        aria-hidden="true"
      >
        {session.title.charAt(0).toUpperCase()}
      </span>
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <p className="truncate text-sm font-semibold text-text-primary">
            {session.title}
          </p>
          {isLive && (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-xs font-semibold text-success">
              <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
              LIVE
            </span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-text-muted">Live Meeting</p>
        <p className="mt-1 text-xs text-text-muted">
          {timeRange(session.scheduledAt, session.durationMins)}
        </p>
        <Link
          to={isLive ? `/live/${session.id}` : `/session/${session.id}`}
          className="mt-1.5 inline-block text-sm font-medium text-text-link"
        >
          {isLive ? 'Join now →' : 'View details'}
        </Link>
      </div>
    </div>
  )
}
