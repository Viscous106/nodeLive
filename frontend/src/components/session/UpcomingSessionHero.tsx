import { Calendar, Clock, GraduationCap } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { ClassSession } from '@/types'

export function UpcomingSessionHero({ session }: { session: ClassSession }) {
  const navigate = useNavigate()
  const start = new Date(session.scheduledAt)
  const dateStr = start.toLocaleDateString('en-US', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
  const timeStr = start.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  })
  const ended = session.status === 'ENDED'

  return (
    <div className="overflow-hidden rounded-hero bg-gradient-to-br from-[#DBEAFE] to-[#EFF6FF]">
      <div className="flex flex-col items-start gap-6 p-8 md:flex-row md:items-center md:justify-between">
        <div className="space-y-3">
          <Badge variant="mandatory">
            {ended ? 'Recording available' : 'Upcoming Session'}
          </Badge>
          <h2 className="text-2xl font-bold text-text-primary">
            {session.title}
          </h2>
          <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-text-secondary">
            <span className="flex items-center gap-1.5">
              <Calendar className="h-4 w-4" />
              {dateStr}
            </span>
            <span className="flex items-center gap-1.5">
              <Clock className="h-4 w-4" />
              {ended ? `Held at ${timeStr}` : `Starts at ${timeStr}`}
            </span>
          </div>
        </div>

        <div className="flex flex-col items-center gap-4">
          <span
            className="hidden h-20 w-20 items-center justify-center rounded-full bg-white/60 text-primary md:flex"
            aria-hidden="true"
          >
            <GraduationCap className="h-10 w-10" />
          </span>
          <Button
            variant={ended ? 'primary' : 'danger'}
            size="lg"
            onClick={() => navigate(`/live/${session.id}`)}
          >
            {ended ? 'Watch recording' : 'Join Session'}
          </Button>
        </div>
      </div>
    </div>
  )
}
