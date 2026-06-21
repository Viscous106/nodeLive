import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAdminOverview } from '@/hooks/useAdmin'
import type { SessionStatus } from '@/types'

const STATUS_VARIANT: Record<string, 'new' | 'success' | 'default' | 'danger'> = {
  SCHEDULED: 'new',
  LIVE: 'success',
  ENDED: 'default',
  CANCELLED: 'danger',
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          {label}
        </p>
        <p className="mt-1 text-3xl font-bold text-text-primary">{value}</p>
      </CardContent>
    </Card>
  )
}

export function OverviewTab() {
  const { data, isLoading } = useAdminOverview()

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
        <Skeleton className="h-40" />
      </div>
    )
  }

  if (!data) return null

  const statusEntries = Object.entries(data.sessionsByStatus)

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Members" value={data.members} />
        <StatCard label="Courses" value={data.courses} />
        <StatCard label="Enrollments" value={data.enrollments} />
        <StatCard
          label="Sessions"
          value={statusEntries.reduce((s, [, n]) => s + n, 0)}
        />
      </div>

      {statusEntries.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Sessions by status</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            {statusEntries.map(([s, count]) => (
              <span key={s} className="flex items-center gap-1.5 text-sm">
                <Badge variant={STATUS_VARIANT[s] ?? 'default'}>{s}</Badge>
                <span className="font-semibold text-text-primary">{count}</span>
              </span>
            ))}
          </CardContent>
        </Card>
      )}

      {data.upcomingSessions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Upcoming sessions</CardTitle>
          </CardHeader>
          <CardContent className="divide-y divide-border">
            {data.upcomingSessions.map((s) => (
              <div key={s.id} className="flex items-center justify-between py-2">
                <div>
                  <Link
                    to={`/session/${s.id}`}
                    className="text-sm font-medium text-text-link hover:underline"
                  >
                    {s.title}
                  </Link>
                  <p className="text-xs text-text-muted">
                    {new Date(s.scheduledAt).toLocaleString()}
                  </p>
                </div>
                <Badge variant={STATUS_VARIANT[s.status as SessionStatus] ?? 'default'}>
                  {s.status}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {data.upcomingSessions.length === 0 &&
        statusEntries.reduce((s, [, n]) => s + n, 0) === 0 && (
          <p className="text-sm text-text-muted">No sessions scheduled yet.</p>
        )}
    </div>
  )
}
