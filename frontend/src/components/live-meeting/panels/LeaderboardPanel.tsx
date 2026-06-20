import { useLiveClassStore } from '@/stores/liveClassStore'

const MEDALS = ['🥇', '🥈', '🥉']

export function LeaderboardPanel({ userId }: { userId: string | undefined }) {
  const leaderboard = useLiveClassStore((s) => s.leaderboard)
  const myScore = useLiveClassStore((s) => s.myScore)

  return (
    <div className="space-y-2 p-4">
      <p className="text-sm text-white/60">Your score: {myScore}</p>
      {leaderboard.length === 0 ? (
        <p className="pt-6 text-center text-sm text-white/50">
          No points yet — answer a quiz or poll.
        </p>
      ) : (
        leaderboard.map((row, i) => (
          <div
            key={row.userId}
            className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm ${
              row.userId === userId ? 'bg-primary/20 text-white' : 'bg-white/5 text-white/80'
            }`}
          >
            <span className="flex items-center gap-2">
              <span className="w-6 text-center">{MEDALS[i] ?? `#${i + 1}`}</span>
              {row.displayName}
            </span>
            <span className="font-semibold">{row.points}</span>
          </div>
        ))
      )}
    </div>
  )
}
