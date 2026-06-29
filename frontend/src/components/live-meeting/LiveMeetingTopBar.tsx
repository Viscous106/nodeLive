import { ArrowLeft, Menu } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useLiveClassStore } from '@/stores/liveClassStore'
import type { ClassSession } from '@/types'

interface Props {
  session: ClassSession | undefined
  onLeave: () => void
  showPanel: boolean
  onTogglePanel: () => void
}

export function LiveMeetingTopBar({ session, onLeave, showPanel, onTogglePanel }: Props) {
  const attendeeCount = useLiveClassStore((s) => s.attendeeCount)

  return (
    <header className="relative z-10 flex h-12 shrink-0 items-center justify-between bg-[#1A1A2E] px-4 text-white">
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

      <div className="flex shrink-0 items-center gap-3">
        <span className="flex items-center gap-1.5 whitespace-nowrap text-sm font-medium text-danger">
          <span className="h-2 w-2 animate-pulse rounded-full bg-danger" />
          LIVE
        </span>
        <span className="whitespace-nowrap text-sm text-white/70">Attendees: {attendeeCount}</span>
        <button
          onClick={onTogglePanel}
          className={`rounded p-1.5 hover:bg-white/10 ${showPanel ? 'text-white' : 'text-white/50'}`}
          title={showPanel ? 'Hide panel' : 'Show panel'}
          aria-label="Toggle side panel"
        >
          <Menu size={18} />
        </button>
        <Button variant="danger" size="sm" onClick={onLeave}>
          Leave
        </Button>
      </div>
    </header>
  )
}
