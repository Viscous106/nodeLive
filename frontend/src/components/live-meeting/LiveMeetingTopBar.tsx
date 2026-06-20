import { ArrowLeft } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useLiveClassStore } from '@/stores/liveClassStore'
import type { ClassSession } from '@/types'

interface Props {
  session: ClassSession | undefined
  onLeave: () => void
}

export function LiveMeetingTopBar({ session, onLeave }: Props) {
  const attendeeCount = useLiveClassStore((s) => s.attendeeCount)

  return (
    <header className="flex h-12 shrink-0 items-center justify-between bg-[#1A1A2E] px-4 text-white">
      <div className="flex min-w-0 items-center gap-3">
        <button
          onClick={onLeave}
          className="rounded p-1 text-white/70 hover:bg-white/10 hover:text-white"
          aria-label="Leave meeting"
        >
          <ArrowLeft size={18} />
        </button>
        <span className="truncate text-sm font-semibold">
          {session?.title ?? 'Live session'}
        </span>
      </div>

      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1.5 text-sm font-medium text-red-400">
          <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
          LIVE
        </span>
        <span className="text-sm text-white/70">Attendees: {attendeeCount}</span>
        <Button variant="danger" size="sm" onClick={onLeave}>
          Leave
        </Button>
      </div>
    </header>
  )
}
