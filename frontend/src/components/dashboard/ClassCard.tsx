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
  return (
    <div className="flex items-start gap-3 rounded-card border border-border bg-card p-4 transition-all hover:border-primary/40 hover:shadow-card">
      <span
        className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary"
        aria-hidden="true"
      >
        {session.title.charAt(0).toUpperCase()}
      </span>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-text-primary">
          {session.title}
        </p>
        <p className="mt-0.5 text-xs text-text-muted">Live Meeting</p>
        <p className="mt-1 text-xs text-text-muted">
          {timeRange(session.scheduledAt, session.durationMins)}
        </p>
        <Link
          to={`/session/${session.id}`}
          className="mt-1.5 inline-block text-sm font-medium text-text-link"
        >
          View details
        </Link>
      </div>
    </div>
  )
}
