import { BookOpen, Calendar, GraduationCap, Users } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAdminOverview } from '@/hooks/useAdmin'

function StatCard({
  label,
  value,
  icon: Icon,
  sub,
}: {
  label: string
  value: number | undefined
  icon: React.ElementType
  sub?: string
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 pt-5">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <p className="text-2xl font-bold text-text-primary">
            {value ?? <Skeleton className="h-7 w-10" />}
          </p>
          <p className="text-sm text-text-muted">{label}</p>
          {sub && <p className="mt-0.5 text-xs text-text-muted">{sub}</p>}
        </div>
      </CardContent>
    </Card>
  )
}

const STATUS_VARIANT = {
  SCHEDULED: 'new',
  LIVE: 'success',
  ENDED: 'default',
  CANCELLED: 'danger',
} as const

export function OverviewTab() {
  const { data, isLoading } = useAdminOverview()

  return (
    <div className="space-y-6">
      {/* stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total members"
          value={data?.totalMembers}
          icon={Users}
          sub={
            data
              ? `${data.students} students · ${data.instructors} instructors · ${data.admins} admins`
              : undefined
          }
        />
        <StatCard
          label="Courses"
          value={data?.totalCourses}
          icon={BookOpen}
        />
        <StatCard
          label="Enrollments"
          value={data?.totalEnrollments}
          icon={GraduationCap}
        />
        <StatCard
          label="Sessions"
          value={
            data
              ? data.sessions.scheduled +
                data.sessions.live +
                data.sessions.ended +
                data.sessions.cancelled
              : undefined
          }
          icon={Calendar}
          sub={
            data
              ? `${data.sessions.scheduled} scheduled · ${data.sessions.live} live · ${data.sessions.ended} ended`
              : undefined
          }
        />
      </div>

      {/* sessions by status */}
      <Card>
        <CardHeader>
          <CardTitle>Sessions by status</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex gap-3">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-8 w-24" />
              ))}
            </div>
          ) : (
            <div className="flex flex-wrap gap-3">
              {(
                [
                  ['SCHEDULED', data?.sessions.scheduled ?? 0],
                  ['LIVE', data?.sessions.live ?? 0],
                  ['ENDED', data?.sessions.ended ?? 0],
                  ['CANCELLED', data?.sessions.cancelled ?? 0],
                ] as const
              ).map(([s, count]) => (
                <div key={s} className="flex items-center gap-2">
                  <Badge variant={STATUS_VARIANT[s]}>{s}</Badge>
                  <span className="text-sm font-semibold text-text-primary">
                    {count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* upcoming sessions */}
      <Card>
        <CardHeader>
          <CardTitle>Upcoming sessions</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          )}
          {!isLoading && data?.upcoming.length === 0 && (
            <p className="py-4 text-center text-sm text-text-muted">
              No upcoming sessions scheduled.
            </p>
          )}
          {!isLoading && data && data.upcoming.length > 0 && (
            <div className="divide-y divide-border">
              {data.upcoming.map((s) => (
                <div key={s.id} className="flex items-center gap-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-text-primary">
                      {s.title}
                    </p>
                    <p className="text-xs text-text-muted">
                      {new Date(s.scheduledAt).toLocaleString()} · {s.durationMins}m
                    </p>
                  </div>
                  <Badge variant={STATUS_VARIANT[s.status as keyof typeof STATUS_VARIANT] ?? 'default'}>
                    {s.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
