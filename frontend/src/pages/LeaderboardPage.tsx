import { Trophy } from 'lucide-react'

import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Avatar } from '@/components/ui/avatar'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/hooks/useAuth'
import { useLeaderboard } from '@/hooks/useLeaderboard'
import { cn } from '@/lib/utils'

const MEDALS = ['🥇', '🥈', '🥉']

export default function LeaderboardPage() {
  const { user } = useAuth()
  const { data, isLoading } = useLeaderboard()

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Leaderboard</h1>
          <p className="mt-1 text-sm text-text-muted">
            Points earned across live quizzes and polls.
          </p>
        </div>

        {isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : data && data.length > 0 ? (
          <Card className="divide-y divide-border overflow-hidden">
            {data.map((entry, i) => {
              const isMe = entry.userId === user?.id
              return (
                <div
                  key={entry.userId}
                  className={cn(
                    'flex items-center gap-3 px-4 py-3',
                    isMe && 'bg-primary/5',
                  )}
                >
                  <span className="w-8 shrink-0 text-center text-sm font-semibold text-text-muted">
                    {MEDALS[i] ?? `#${i + 1}`}
                  </span>
                  <Avatar name={entry.displayName} />
                  <span className="flex-1 truncate text-sm font-medium text-text-primary">
                    {entry.displayName}
                    {isMe && <span className="text-text-muted"> (you)</span>}
                  </span>
                  <span className="text-sm font-semibold text-text-primary">
                    {entry.points} pts
                  </span>
                </div>
              )
            })}
          </Card>
        ) : (
          <div className="flex flex-col items-center gap-2 rounded-card border border-border bg-card py-12 text-center">
            <Trophy className="h-8 w-8 text-text-muted" />
            <p className="text-sm text-text-muted">
              No points yet — they’ll appear after live quizzes and polls.
            </p>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
