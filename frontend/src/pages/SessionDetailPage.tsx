import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { SkipLink } from '@/components/layout/SkipLink'
import { TopNav } from '@/components/layout/TopNav'
import { AssignmentTab } from '@/components/session/AssignmentTab'
import { SessionTabBar } from '@/components/session/SessionTabBar'
import type { SessionTab } from '@/components/session/SessionTabBar'
import { SimilarSessionsRow } from '@/components/session/SimilarSessionsRow'
import { UpcomingSessionHero } from '@/components/session/UpcomingSessionHero'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useSession } from '@/hooks/useSession'

function TabPlaceholder({ text }: { text: string }) {
  return (
    <div className="rounded-card border border-border bg-card p-10 text-center text-sm text-text-muted">
      {text}
    </div>
  )
}

function NotFound() {
  return (
    <div className="flex flex-col items-center gap-3 py-20 text-center">
      <h1 className="text-xl font-semibold text-text-primary">
        Session not found
      </h1>
      <p className="text-sm text-text-muted">
        It may have been removed, or the link is wrong.
      </p>
      <Link to="/dashboard">
        <Button>Back to dashboard</Button>
      </Link>
    </div>
  )
}

export default function SessionDetailPage() {
  const { sessionId = '' } = useParams()
  const { data: session, isLoading, isError } = useSession(sessionId)
  const [tab, setTab] = useState<SessionTab>('Session')

  return (
    <div className="min-h-screen bg-page">
      <SkipLink />
      <TopNav />
      <main
        id="main-content"
        className="mx-auto max-w-[1100px] px-4 py-6 sm:px-page-x"
      >
        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-10 w-72" />
            <Skeleton className="h-[220px] w-full rounded-hero" />
          </div>
        ) : isError || !session ? (
          <NotFound />
        ) : (
          <>
            <div className="mb-4 flex items-center gap-2">
              <Link
                to="/dashboard"
                aria-label="Back to dashboard"
                className="rounded-btn p-1.5 text-text-secondary hover:bg-border-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
              >
                <ArrowLeft className="h-5 w-5" />
              </Link>
              <h1 className="truncate text-xl font-semibold text-text-primary">
                {session.title}
              </h1>
            </div>

            <SessionTabBar status={session.status} active={tab} onChange={setTab} />

            <div className="mt-6 space-y-8">
              {tab === 'Session' && (
                <>
                  <UpcomingSessionHero session={session} />
                  <SimilarSessionsRow sessionId={session.id} />
                </>
              )}
              {tab === 'Assignment' && <AssignmentTab session={session} />}
              {tab === 'Feedback' && (
                <TabPlaceholder text="Feedback opens once the session has ended." />
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
