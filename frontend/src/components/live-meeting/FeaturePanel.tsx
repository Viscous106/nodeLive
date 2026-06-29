import { useState } from 'react'

import {
  Bookmark,
  BarChart3,
  FileText,
  MessageSquare,
  Target,
  Trophy,
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
  { id: 'leaderboard', icon: Trophy, label: 'Board' },
  { id: 'bookmarks', icon: Bookmark, label: 'Marks' },
  { id: 'notes', icon: FileText, label: 'Notes' },
]

interface Props {
  sessionId: string
  user: User | null
  isInstructor: boolean
  joinedAt: number
}

export function FeaturePanel({ sessionId, user, isInstructor, joinedAt }: Props) {
  const [tab, setTab] = useState<TabId>('chat')

  return (
    <aside className="flex w-[360px] shrink-0 flex-col bg-[#1A1A2E] text-white">
      <nav role="tablist" aria-label="Class tools" className="flex border-b border-white/10">
        {TABS.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={cn(
              'flex flex-1 flex-col items-center gap-1 border-b-2 py-2 text-[11px] focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/40',
              tab === id
                ? 'border-primary-light text-primary-light'
                : 'border-transparent text-white/50 hover:text-white/80',
            )}
          >
            <Icon size={18} />
            {label}
          </button>
        ))}
      </nav>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {tab === 'chat' && (
          <ChatPanel sessionId={sessionId} user={user} isInstructor={isInstructor} />
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
    </aside>
  )
}
