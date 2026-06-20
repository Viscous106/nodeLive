import { Calendar } from 'lucide-react'

import { ClassCard } from '@/components/dashboard/ClassCard'
import { VideoCard } from '@/components/dashboard/VideoCard'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Skeleton } from '@/components/ui/skeleton'
import { usePastSessions, useUpcomingSessions } from '@/hooks/useDashboard'

function Empty({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-card border border-border bg-card py-10 text-center">
      <Calendar className="h-8 w-8 text-text-muted" />
      <p className="text-sm text-text-muted">{text}</p>
    </div>
  )
}

export default function SessionsPage() {
  const { data: upcoming, isLoading: loadingUpcoming } = useUpcomingSessions()
  const { data: past, isLoading: loadingPast } = usePastSessions()

  return (
    <DashboardLayout>
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Sessions</h1>
          <p className="mt-1 text-sm text-text-muted">
            Your upcoming classes and past recordings.
          </p>
        </div>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-text-primary">Upcoming</h2>
          {loadingUpcoming ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <Skeleton className="h-28" />
              <Skeleton className="h-28" />
            </div>
          ) : upcoming && upcoming.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {upcoming.map((s) => (
                <ClassCard key={s.id} session={s} />
              ))}
            </div>
          ) : (
            <Empty text="No upcoming sessions." />
          )}
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-text-primary">Past</h2>
          {loadingPast ? (
            <div className="flex gap-4">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-[210px] w-[250px] shrink-0" />
              ))}
            </div>
          ) : past && past.length > 0 ? (
            <div className="flex flex-wrap gap-4">
              {past.map((s) => (
                <VideoCard key={s.id} session={s} />
              ))}
            </div>
          ) : (
            <Empty text="No past sessions yet." />
          )}
        </section>
      </div>
    </DashboardLayout>
  )
}
