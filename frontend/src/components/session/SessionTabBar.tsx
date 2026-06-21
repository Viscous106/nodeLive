import { Lock } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { SessionStatus } from '@/types'

export const SESSION_TABS = ['Session', 'Assignment', 'Notes', 'Feedback'] as const
export type SessionTab = (typeof SESSION_TABS)[number] | 'Analytics'

export function SessionTabBar({
  tabs = SESSION_TABS,
  status,
  active,
  onChange,
}: {
  tabs?: readonly SessionTab[]
  status: SessionStatus
  active: SessionTab
  onChange: (tab: SessionTab) => void
}) {
  return (
    <div className="flex gap-4 overflow-x-auto border-b border-border sm:gap-6">
      {tabs.map((tab) => {
        const locked = tab === 'Feedback' && status !== 'ENDED'
        return (
          <button
            key={tab}
            type="button"
            disabled={locked}
            onClick={() => onChange(tab)}
            aria-current={active === tab ? 'page' : undefined}
            className={cn(
              'relative -mb-px flex shrink-0 items-center gap-1.5 border-b-2 py-3 text-sm font-medium whitespace-nowrap transition-colors',
              active === tab
                ? 'border-primary text-primary'
                : 'border-transparent text-text-muted hover:text-text-secondary',
              locked && 'cursor-not-allowed opacity-50 hover:text-text-muted',
            )}
          >
            {tab}
            {locked && <Lock className="h-3.5 w-3.5" />}
          </button>
        )
      })}
    </div>
  )
}
