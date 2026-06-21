import { useState } from 'react'

import { EnrollmentsTab } from '@/components/admin/EnrollmentsTab'
import { MembersTab } from '@/components/admin/MembersTab'
import { OverviewTab } from '@/components/admin/OverviewTab'
import { SessionsTab } from '@/components/admin/SessionsTab'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { cn } from '@/lib/utils'

type TabKey = 'overview' | 'members' | 'sessions' | 'enrollments'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'sessions', label: 'Sessions' },
  { key: 'members', label: 'Members & roles' },
  { key: 'enrollments', label: 'Enrollments' },
]

export default function AdminPage() {
  const [tab, setTab] = useState<TabKey>('overview')

  return (
    <DashboardLayout>
      <div className="space-y-1">
        <h1 className="text-2xl font-bold text-text-primary">Admin</h1>
        <p className="text-sm text-text-secondary">
          Manage members, roles, and scheduled sessions for your organization.
        </p>
      </div>

      <div
        role="tablist"
        aria-label="Admin sections"
        className="mt-5 flex gap-1 border-b border-border"
      >
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              '-mb-px border-b-2 px-4 py-2 text-sm font-semibold transition-colors',
              tab === t.key
                ? 'border-primary text-primary'
                : 'border-transparent text-text-secondary hover:text-text-primary',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {tab === 'overview' && <OverviewTab />}
        {tab === 'sessions' && <SessionsTab />}
        {tab === 'members' && <MembersTab />}
        {tab === 'enrollments' && <EnrollmentsTab />}
      </div>
    </DashboardLayout>
  )
}
