import { Calendar, FileText } from 'lucide-react'

import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

// Sections render their populated state in M2 (timetable, continue-watching,
// performance + notices from /api/dashboard/widgets). M1 ships the shell with
// honest empty states.

function weekDays(): { label: string; date: number; isToday: boolean }[] {
  const today = new Date()
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(today)
    d.setDate(today.getDate() + i)
    return {
      label: d.toLocaleDateString('en-US', { weekday: 'short' }),
      date: d.getDate(),
      isToday: i === 0,
    }
  })
}

function DateStrip() {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
      {weekDays().map((d, i) => (
        <div
          key={i}
          className={cn(
            'flex min-w-[52px] flex-col items-center rounded-lg border px-3 py-2',
            d.isToday
              ? 'border-primary bg-primary/5 text-primary'
              : 'border-border text-text-secondary',
          )}
        >
          <span className="text-xs font-medium">{d.label}</span>
          <span className="text-base font-semibold">{d.date}</span>
        </div>
      ))}
    </div>
  )
}

function EmptyState({ icon: Icon, text }: { icon: typeof Calendar; text: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <Icon className="h-8 w-8 text-text-muted" />
      <p className="text-sm text-text-muted">{text}</p>
    </div>
  )
}

function ProgressRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-text-secondary">{label}</span>
        <span className="font-semibold text-text-primary">{value}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-border-muted">
        <div className="h-full w-0 rounded-full bg-success-light" />
      </div>
    </div>
  )
}

function Sidebar() {
  return (
    <div className="space-y-4">
      <div className="rounded-card bg-gradient-to-br from-dark-banner to-[#312E81] p-4 text-white">
        <p className="text-sm font-semibold">Your year at linkHQ</p>
        <p className="mt-1 text-xs text-white/70">
          Recap arrives once you’ve attended your first sessions.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Performance</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <ProgressRow label="Attendance" value="—" />
          <ProgressRow label="Problems solved" value="—" />
        </CardContent>
      </Card>

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

export default function DashboardPage() {
  const { user } = useAuth()
  const firstName = user?.displayName.split(' ')[0] ?? 'there'

  return (
    <DashboardLayout sidebar={<Sidebar />}>
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            Welcome back, {firstName}
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Here’s what’s happening in your courses.
          </p>
        </div>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-text-primary">Time Table</h2>
          <Card>
            <CardContent className="space-y-4 pt-4">
              <DateStrip />
              <EmptyState icon={Calendar} text="No classes scheduled for today." />
            </CardContent>
          </Card>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-text-primary">
            Continue Watching
          </h2>
          <Card>
            <CardContent className="pt-4">
              <EmptyState
                icon={FileText}
                text="Nothing in progress yet — your recordings will show up here."
              />
            </CardContent>
          </Card>
        </section>
      </div>
    </DashboardLayout>
  )
}
