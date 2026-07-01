import { useLiveClassStore } from '@/stores/liveClassStore'

const MEDALS = ['🥇', '🥈', '🥉']

export function LeaderboardPanel({ userId }: { userId: string | undefined }) {
  const leaderboard = useLiveClassStore((s) => s.leaderboard)
  const myScore = useLiveClassStore((s) => s.myScore)

  return (
    <div className="space-y-2 p-4">
      <p className="text-sm text-gray-600">Your score: {myScore}</p>
      {leaderboard.length === 0 ? (
        <p className="pt-4 text-center text-sm text-gray-500">
          No points yet — answer a quiz or poll.
        </p>
      ) : (
        leaderboard.map((row, i) => (
          <div
            key={row.userId}
            className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm ${
              row.userId === userId ? 'bg-primary/20 text-gray-900' : 'bg-gray-50 text-gray-700'
            }`}
          >
            <span className="flex min-w-0 items-center gap-2">
              <span className="w-6 shrink-0 text-center">{MEDALS[i] ?? `#${i + 1}`}</span>
              <span className="truncate">{row.displayName}</span>
            </span>
            <span className="shrink-0 pl-2 font-semibold">{row.points}</span>
          </div>
        ))
      )}
    </div>
  )
}
