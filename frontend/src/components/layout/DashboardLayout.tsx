import type { ReactNode } from 'react'

import { SideDrawer } from './SideDrawer'
import { TopNav } from './TopNav'

export function DashboardLayout({
  children,
  sidebar,
}: {
  children: ReactNode
  sidebar?: ReactNode
}) {
  return (
    <div className="min-h-screen bg-page">
      <TopNav />
      <SideDrawer />
      <main className="mx-auto flex max-w-[1400px] gap-6 px-4 py-6 sm:px-page-x">
        <div className="min-w-0 flex-1">{children}</div>
        {sidebar && (
          <aside className="hidden w-[300px] shrink-0 lg:block">{sidebar}</aside>
        )}
      </main>
    </div>
  )
}
