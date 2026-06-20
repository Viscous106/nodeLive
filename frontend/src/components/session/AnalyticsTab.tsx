import { Avatar } from '@/components/ui/avatar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useSessionAnalytics } from '@/hooks/useAnalytics'

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="pt-4">
        <p className="text-2xl font-bold text-text-primary">{value}</p>
        <p className="mt-1 text-xs text-text-muted">{label}</p>
      </CardContent>
    </Card>
  )
}

export function AnalyticsTab({ sessionId }: { sessionId: string }) {
  const { data, isLoading } = useSessionAnalytics(sessionId)

  if (isLoading || !data) {
    return <Skeleton className="h-48 w-full" />
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Stat label="Enrolled" value={data.enrolled} />
        <Stat label="Quiz participants" value={data.quizParticipants} />
        <Stat label="Quiz answers" value={data.quizResponses} />
        <Stat label="Poll responses" value={data.pollResponses} />
        <Stat label="Avg quiz points" value={data.avgQuizPoints} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Top scorers</CardTitle>
        </CardHeader>
        <CardContent>
          {data.topScorers.length > 0 ? (
            <div className="space-y-2">
              {data.topScorers.map((u, i) => (
                <div key={u.userId} className="flex items-center gap-3">
                  <span className="w-6 text-center text-sm font-semibold text-text-muted">
                    #{i + 1}
                  </span>
                  <Avatar name={u.displayName} />
                  <span className="flex-1 truncate text-sm font-medium text-text-primary">
                    {u.displayName}
                  </span>
                  <span className="text-sm font-semibold text-text-primary">
                    {u.points} pts
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-text-muted">No quiz/poll activity yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
