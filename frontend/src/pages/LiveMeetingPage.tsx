import { useEffect, useRef, useState } from 'react'

import { useNavigate, useParams } from 'react-router-dom'

import { FeaturePanel } from '@/components/live-meeting/FeaturePanel'
import { LiveMeetingTopBar } from '@/components/live-meeting/LiveMeetingTopBar'
import { ZoomPanel } from '@/components/live-meeting/ZoomPanel'
import { CueCardOverlay } from '@/components/live-meeting/overlays/CueCardOverlay'
import { NoticeOverlay } from '@/components/live-meeting/overlays/NoticeOverlay'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { PageLoader } from '@/components/ui/PageLoader'
import { Spinner } from '@/components/ui/spinner'
import { useAuth } from '@/hooks/useAuth'
import { useLiveState } from '@/hooks/useLiveState'
import { useSession } from '@/hooks/useSession'
import { useSocket } from '@/hooks/useSocket'
import { useSocketEvents } from '@/hooks/useSocketEvents'
import { useZoomSDK } from '@/hooks/useZoomSDK'
import { api } from '@/lib/api'
import { useLiveClassStore } from '@/stores/liveClassStore'
import { toast } from '@/stores/toastStore'

export default function LiveMeetingPage() {
  const { sessionId = '' } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { data: session, isLoading } = useSession(sessionId)
  const rootRef = useRef<HTMLDivElement>(null)
  const joinedAt = useRef(Date.now())

  useLiveState(sessionId)
  useSocket(sessionId)
  useSocketEvents(sessionId)

  const [confirmingLeave, setConfirmingLeave] = useState(false)
  const [ending, setEnding] = useState(false)
  // Open the side panel (Chat tab) by default so the AI chat / class tools are
  // visible on entry; the hamburger in the top bar still toggles it.
  const [showPanel, setShowPanel] = useState(true)

  const { status, errorMsg, joinMeeting, leaveMeeting } = useZoomSDK(
    rootRef,
    sessionId,
    user ?? null,
    Boolean(session && user && session.hostId === user.id),
  )

  const reset = useLiveClassStore((s) => s.reset)
  const tick = useLiveClassStore((s) => s.tick)
  const activeQuestion = useLiveClassStore((s) => s.activeQuestion)
  const sessionEnded = useLiveClassStore((s) => s.sessionEnded)

  // Cosmetic per-second countdown; re-synced by each quiz:next-question event.
  useEffect(() => {
    if (!activeQuestion) return
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [activeQuestion, tick])

  // Clear live state when leaving the page.
  useEffect(() => reset, [reset])

  const isInstructor = Boolean(
    user && (user.role !== 'STUDENT' || session?.hostId === user.id),
  )

  // Leave the Zoom call but keep the session LIVE (host can rejoin; students
  // are simply leaving). This is the only action for students.
  const justLeave = async () => {
    setConfirmingLeave(false)
    await leaveMeeting()
    navigate('/dashboard')
  }

  // Host ends the class for everyone: flip the session to ENDED server-side.
  // On success the backend broadcasts `session:ended`, which the effect below
  // turns into leave + navigate (for the host AND every other participant).
  const endClass = async () => {
    setEnding(true)
    try {
      await api.post(`/api/sessions/${sessionId}/live/end`)
    } catch {
      toast({ variant: 'error', title: 'Could not end the class — try again' })
      setEnding(false)
    }
  }

  // When the session is ended (by this host or another instructor), drop out of
  // the meeting and return to the dashboard.
  useEffect(() => {
    if (!sessionEnded) return
    void (async () => {
      await leaveMeeting()
      navigate('/dashboard')
    })()
  }, [sessionEnded, leaveMeeting, navigate])

  if (isLoading) return <PageLoader />

  if (session && session.status !== 'LIVE' && !isInstructor) {
    const ended = session.status === 'ENDED' || session.status === 'CANCELLED'
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-[#1A1A2E] text-white">
        {!ended && <Spinner className="h-10 w-10 text-white" />}
        <div className="text-center">
          <p className="text-lg font-semibold">
            {ended
              ? 'This class has ended.'
              : 'Waiting for the host to start the class…'}
          </p>
          {!ended && (
            <p className="mt-1 text-sm text-white/60">
              You'll join automatically the moment the host starts.
            </p>
          )}
        </div>
        <button
          onClick={() => navigate('/dashboard')}
          className="rounded text-sm text-primary-light hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          Back to dashboard
        </button>
      </div>
    )
  }

  // `fixed` + explicit height is the only reliable way to prevent document-level
  // scroll (`h-screen overflow-hidden` still scrolls because the Zoom SDK's
  // fixed-position elements escape overflow clipping). We use `h-[100dvh]`
  // (dynamic viewport height) rather than `inset-0` so that on mobile the bottom
  // edge tracks the VISIBLE viewport — otherwise the Zoom control toolbar lands
  // behind the browser's address/nav bar. On desktop 100dvh == 100vh.
  return (
    <div className="fixed inset-x-0 top-0 flex h-[100dvh] flex-col bg-black">
      <LiveMeetingTopBar
        session={session}
        onLeave={() => setConfirmingLeave(true)}
        showPanel={showPanel}
        onTogglePanel={() => setShowPanel((v) => !v)}
      />
      <div className="flex min-h-0 flex-1">
        <div className="relative flex flex-1">
          <ZoomPanel
            rootRef={rootRef}
            status={status}
            errorMsg={errorMsg}
            onJoin={joinMeeting}
            hasZoomMeeting={!!session?.zoomMeetingId}
            canStart={!!session && session.hostId === user?.id}
          />
          <CueCardOverlay />
        </div>
        {showPanel && (
          <FeaturePanel
            sessionId={sessionId}
            user={user}
            isInstructor={isInstructor}
            joinedAt={joinedAt.current}
          />
        )}
      </div>
      <NoticeOverlay />
      {isInstructor ? (
        <ConfirmDialog
          open={confirmingLeave}
          title="End the class?"
          description="Ending stops the class for everyone and records attendance. You can also just leave and rejoin while it stays live."
          confirmLabel={ending ? 'Ending…' : 'End for everyone'}
          confirmDisabled={ending}
          onConfirm={endClass}
          secondaryLabel="Just leave"
          onSecondary={justLeave}
          onCancel={() => setConfirmingLeave(false)}
        />
      ) : (
        <ConfirmDialog
          open={confirmingLeave}
          title="Leave the class?"
          description="You can rejoin while the session is live."
          confirmLabel="Leave"
          onConfirm={justLeave}
          onCancel={() => setConfirmingLeave(false)}
        />
      )}
    </div>
  )
}
