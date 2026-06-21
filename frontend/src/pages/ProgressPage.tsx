import { BarChart2, BookOpen, ChevronDown, ChevronRight, Video } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useMyProgress } from '@/hooks/useDashboard'
import type {
  AssignmentProgressItem,
  CourseProgressItem,
  SessionProgressItem,
} from '@/hooks/useDashboard'

// ─── helpers ────────────────────────────────────────────────────────────────

function statusVariant(
  status: AssignmentProgressItem['status'],
): 'success' | 'warning' | 'default' {
  if (status === 'GRADED') return 'success'
  if (status === 'SUBMITTED') return 'warning'
  return 'default'
}

function statusLabel(status: AssignmentProgressItem['status']): string {
  if (status === 'GRADED') return 'Graded'
  if (status === 'SUBMITTED') return 'Submitted'
  return 'Pending'
}

function sessionStatusVariant(
  s: string,
): 'success' | 'danger' | 'warning' | 'default' {
  if (s === 'ENDED') return 'success'
  if (s === 'LIVE') return 'danger'
  if (s === 'SCHEDULED') return 'warning'
  return 'default'
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

// ─── sub-components ──────────────────────────────────────────────────────────

function WatchBar({ pct }: { pct: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-border-muted">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-xs text-text-muted">{Math.round(pct)}%</span>
    </div>
  )
}

function AssignmentRow({ a }: { a: AssignmentProgressItem }) {
  return (
    <div className="flex flex-col gap-1 border-b border-border px-4 py-3 last:border-0 sm:flex-row sm:items-center sm:gap-4">
      <span className="flex-1 text-sm font-medium text-text-primary">{a.title}</span>
      <div className="flex items-center gap-3 sm:contents">
        <span className="text-xs text-text-muted">
          {a.dueAt ? `Due ${fmtDate(a.dueAt)}` : 'No due date'}
        </span>
        <Badge variant={statusVariant(a.status)}>{statusLabel(a.status)}</Badge>
        {a.status === 'GRADED' && a.grade !== null ? (
          <span className="text-sm font-semibold text-text-primary">
            {a.grade}/{a.maxPoints}
          </span>
        ) : (
          <span className="text-sm text-text-muted">—/{a.maxPoints}</span>
        )}
      </div>
    </div>
  )
}

function SessionRow({ s }: { s: SessionProgressItem }) {
  return (
    <div className="flex flex-col gap-1 border-b border-border px-4 py-3 last:border-0 sm:flex-row sm:items-center sm:gap-4">
      <Link
        to={`/session/${s.id}`}
        className="flex-1 text-sm font-medium text-text-link hover:underline"
      >
        {s.title}
      </Link>
      <div className="flex items-center gap-3 sm:contents">
        <span className="text-xs text-text-muted">{fmtDate(s.scheduledAt)}</span>
        <Badge variant={sessionStatusVariant(s.sessionStatus)}>
          {s.sessionStatus}
        </Badge>
        {s.watchPercent !== null ? (
          <WatchBar pct={s.watchPercent} />
        ) : (
          <span className="text-xs text-text-muted">No recording</span>
        )}
      </div>
    </div>
  )
}

function CourseSection({ course }: { course: CourseProgressItem }) {
  const [open, setOpen] = useState(true)
  const submitted = course.assignments.filter((a) => a.status !== null).length
  const graded = course.assignments.filter((a) => a.status === 'GRADED').length
  const grades = course.assignments
    .filter((a) => a.grade !== null)
    .map((a) => a.grade as number)
  const avg = grades.length > 0 ? Math.round(grades.reduce((s, g) => s + g, 0) / grades.length) : null

  return (
    <Card>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
      >
        <div className="flex items-center gap-3">
          <BookOpen className="h-4 w-4 shrink-0 text-primary" />
          <span className="text-base font-semibold text-text-primary">{course.title}</span>
          <div className="hidden items-center gap-2 sm:flex">
            <span className="text-xs text-text-muted">
              {submitted}/{course.assignments.length} submitted
            </span>
            {avg !== null && (
              <span className="text-xs font-semibold text-success">avg {avg}%</span>
            )}
          </div>
        </div>
        {open ? (
          <ChevronDown className="h-4 w-4 text-text-muted" />
        ) : (
          <ChevronRight className="h-4 w-4 text-text-muted" />
        )}
      </button>

      {open && (
        <>
          {course.assignments.length > 0 ? (
            <div className="border-t border-border">
              <p className="px-4 pb-1 pt-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
                Assignments ({graded}/{course.assignments.length} graded)
              </p>
              {course.assignments.map((a) => (
                <AssignmentRow key={a.id} a={a} />
              ))}
            </div>
          ) : (
            <p className="border-t border-border px-4 py-3 text-sm text-text-muted">
              No assignments yet.
            </p>
          )}

          {course.sessions.length > 0 && (
            <div className="border-t border-border">
              <p className="px-4 pb-1 pt-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
                Sessions
              </p>
              {course.sessions.map((s) => (
                <SessionRow key={s.id} s={s} />
              ))}
            </div>
          )}
        </>
      )}
    </Card>
  )
}

// ─── stat card ───────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
}: {
  label: string
  value: string | number
}) {
  return (
    <Card>
      <CardContent className="px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          {label}
        </p>
        <p className="mt-1 text-2xl font-bold text-text-primary">{value}</p>
      </CardContent>
    </Card>
  )
}

// ─── page ────────────────────────────────────────────────────────────────────

export default function ProgressPage() {
  const { data, isLoading } = useMyProgress()

  const avgLabel =
    data?.avgGrade !== null && data?.avgGrade !== undefined
      ? `${data.avgGrade}%`
      : '—'

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <BarChart2 className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold text-text-primary">My Progress</h1>
            <p className="text-sm text-text-muted">
              Assignments, grades, and session watch history.
            </p>
          </div>
        </div>

        {isLoading ? (
          <div className="grid gap-3 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
        ) : data ? (
          <>
            <div className="grid gap-3 sm:grid-cols-4">
              <StatCard label="Courses" value={data.courses.length} />
              <StatCard
                label="Submitted"
                value={`${data.assignmentsSubmitted}/${data.assignmentsTotal}`}
              />
              <StatCard label="Graded" value={data.assignmentsGraded} />
              <StatCard label="Avg Grade" value={avgLabel} />
            </div>

            {data.courses.length === 0 ? (
              <Card>
                <CardContent className="flex flex-col items-center gap-3 py-12">
                  <Video className="h-10 w-10 text-text-muted" />
                  <p className="text-sm text-text-muted">
                    No courses yet. Sessions you join will appear here.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {data.courses.map((c) => (
                  <CourseSection key={c.id} course={c} />
                ))}
              </div>
            )}
          </>
        ) : null}
      </div>
    </DashboardLayout>
  )
}
