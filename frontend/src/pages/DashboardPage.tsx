import { ContinueWatchingSection } from '@/components/dashboard/ContinueWatchingSection'
import { DashboardSidebar } from '@/components/dashboard/DashboardSidebar'
import { TimetableSection } from '@/components/dashboard/TimetableSection'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { useAuth } from '@/hooks/useAuth'

export default function DashboardPage() {
  const { user } = useAuth()
  const firstName = user?.displayName.split(' ')[0] ?? 'there'

  return (
    <DashboardLayout sidebar={<DashboardSidebar />}>
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            Welcome back, {firstName}
          </h1>
          <p className="mt-1 text-sm text-text-muted">
            Here’s what’s happening in your courses.
          </p>
        </div>

        <TimetableSection />
        <ContinueWatchingSection />
      </div>
    </DashboardLayout>
  )
}
