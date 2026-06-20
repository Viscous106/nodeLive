import { BookOpen } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useCourses, useDashboardStats } from '@/hooks/useDashboard'

function ProgressRow({
  label,
  value,
  pct,
}: {
  label: string
  value: string
  pct: number | null
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-text-secondary">{label}</span>
        <span className="font-semibold text-text-primary">{value}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-border-muted">
        <div
          className="h-full rounded-full bg-success-light transition-all"
          style={{ width: `${pct ?? 0}%` }}
        />
      </div>
    </div>
  )
}

function PerformanceWidget() {
  const { data, isLoading } = useDashboardStats()
  const graded = data?.assignmentsGraded ?? 0
  const total = data?.assignmentsTotal ?? 0
  const pct = total > 0 ? Math.round((graded / total) * 100) : 0

  return (
    <Card>
      <CardHeader>
        <CardTitle>Performance</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <Skeleton className="h-12" />
        ) : (
          <>
            {/* Attendance needs the compliance read-model (Dev B M7) — shown as
                — rather than faked. */}
            <ProgressRow label="Attendance" value="—" pct={null} />
            <ProgressRow
              label="Assignments graded"
              value={total > 0 ? `${graded}/${total}` : '—'}
              pct={total > 0 ? pct : null}
            />
          </>
        )}
      </CardContent>
    </Card>
  )
}

function CoursesWidget() {
  const { data, isLoading } = useCourses()
  return (
    <Card>
      <CardHeader>
        <CardTitle>Your Courses</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading ? (
          <>
            <Skeleton className="h-5 w-3/4" />
            <Skeleton className="h-5 w-1/2" />
          </>
        ) : data && data.length > 0 ? (
          data.map((c) => (
            <div key={c.id} className="flex items-center gap-2 text-sm">
              <BookOpen className="h-4 w-4 text-primary" />
              <span className="truncate text-text-secondary">{c.title}</span>
            </div>
          ))
        ) : (
          <p className="text-sm text-text-muted">You’re not enrolled yet.</p>
        )}
      </CardContent>
    </Card>
  )
}

export function DashboardSidebar() {
  return (
    <div className="space-y-4">
      <div className="rounded-card bg-gradient-to-br from-dark-banner to-[#312E81] p-4 text-white">
        <p className="text-sm font-semibold">Your year at linkHQ</p>
        <p className="mt-1 text-xs text-white/70">
          Your recap appears once you’ve attended your first sessions.
        </p>
      </div>

      <CoursesWidget />

      <PerformanceWidget />

      <Card>
        <CardHeader>
          <CardTitle>Notice Board</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-muted">No notices right now.</p>
        </CardContent>
      </Card>
    </div>
  )
}
