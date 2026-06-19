import { Play } from 'lucide-react'
import { Link } from 'react-router-dom'

import { getTopicColor } from '@/lib/topicColor'
import type { ClassSession } from '@/types'

export function VideoCard({ session }: { session: ClassSession }) {
  const color = getTopicColor(session.title)
  const date = new Date(session.scheduledAt).toLocaleDateString('en-US', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })

  return (
    <Link
      to={`/session/${session.id}`}
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
      <div className="flex items-center justify-between p-3">
        <p className="truncate text-sm font-semibold text-text-primary">
          Lecture recording
        </p>
        <span className="text-sm font-medium text-text-link">Resume</span>
      </div>
    </Link>
  )
}
