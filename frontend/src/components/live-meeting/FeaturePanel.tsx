import { useState } from 'react'

import {
  Bookmark,
  BarChart3,
  FileText,
  MessageSquare,
  Target,
  Trophy,
  X,
} from 'lucide-react'

import { ChatPanel } from '@/components/live-meeting/panels/ChatPanel'
import { BookmarkPanel } from '@/components/live-meeting/panels/BookmarkPanel'
import { LeaderboardPanel } from '@/components/live-meeting/panels/LeaderboardPanel'
import { NotesPanel } from '@/components/live-meeting/panels/NotesPanel'
import { PollPanel } from '@/components/live-meeting/panels/PollPanel'
import { QuizPanel } from '@/components/live-meeting/panels/QuizPanel'
import { cn } from '@/lib/utils'
import type { User } from '@/types'

type TabId = 'chat' | 'quiz' | 'poll' | 'leaderboard' | 'bookmarks' | 'notes'

const TABS: { id: TabId; icon: typeof MessageSquare; label: string }[] = [
  { id: 'chat', icon: MessageSquare, label: 'Chat' },
  { id: 'quiz', icon: Target, label: 'Quiz' },
  { id: 'poll', icon: BarChart3, label: 'Poll' },
  { id: 'leaderboard', icon: Trophy, label: 'Leaderboard' },
  { id: 'bookmarks', icon: Bookmark, label: 'Bookmarks' },
  { id: 'notes', icon: FileText, label: 'Notes' },
]

interface Props {
  sessionId: string
  user: User | null
  isInstructor: boolean
  joinedAt: number
}

// Vertical tool rail (right edge) + a light content panel that opens to its
// left. Clicking a tool opens its panel; clicking the active tool again (or the
// ✕) collapses to just the rail so the video reclaims the space. Chat is open
// on entry. Only the nav layout + theme changed here — every panel's logic is
// untouched (they were recoloured to the light theme in their own files).
export function FeaturePanel({ sessionId, user, isInstructor, joinedAt }: Props) {
  const [tab, setTab] = useState<TabId>('chat')
  const [open, setOpen] = useState(true)

  const activeLabel = TABS.find((t) => t.id === tab)?.label ?? ''

  const selectTab = (id: TabId) => {
    // Re-tapping the open tool collapses the panel; anything else opens it.
    if (id === tab && open) {
      setOpen(false)
      return
    }
    setTab(id)
    setOpen(true)
  }

  return (
    <aside className="flex shrink-0">
      {open && (
        <section className="relative z-10 flex w-[300px] flex-col bg-white text-gray-900 shadow-[-8px_0_24px_-10px_rgba(0,0,0,0.55)]">
          <header className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
            <h2 className="text-base font-semibold">{activeLabel}</h2>
            <button
              onClick={() => setOpen(false)}
              aria-label="Close panel"
              className="rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
            >
              <X size={16} />
            </button>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {tab === 'chat' && (
              <ChatPanel
                sessionId={sessionId}
                user={user}
                isInstructor={isInstructor}
              />
            )}
            {tab === 'quiz' && (
              <QuizPanel sessionId={sessionId} isInstructor={isInstructor} />
            )}
            {tab === 'poll' && (
              <PollPanel sessionId={sessionId} isInstructor={isInstructor} />
            )}
            {tab === 'leaderboard' && <LeaderboardPanel userId={user?.id} />}
            {tab === 'bookmarks' && (
              <BookmarkPanel sessionId={sessionId} joinedAt={joinedAt} />
            )}
            {tab === 'notes' && (
              <NotesPanel sessionId={sessionId} isInstructor={isInstructor} />
            )}
          </div>
        </section>
      )}

      <nav
        role="tablist"
        aria-label="Class tools"
        className="flex w-[72px] shrink-0 flex-col gap-1 border-l border-white/[0.07] bg-[#1E2127] p-2"
      >
        {TABS.map(({ id, icon: Icon, label }) => {
          const active = tab === id && open
          return (
            <button
              key={id}
              role="tab"
              aria-selected={active}
              onClick={() => selectTab(id)}
              className={cn(
                'flex flex-col items-center gap-1 rounded-lg px-1 py-2.5 text-[11px] leading-tight transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/40',
                active
                  ? 'bg-[#2A2E36] text-[#60A5FA]'
                  : 'text-gray-400 hover:bg-white/[0.05] hover:text-white',
              )}
            >
              <Icon size={18} />
              <span className="text-center">{label}</span>
            </button>
          )
        })}
      </nav>
    </aside>
  )
}
