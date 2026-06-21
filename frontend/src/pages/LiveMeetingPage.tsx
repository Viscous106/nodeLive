import { useEffect, useRef, useState } from 'react'

import { useNavigate, useParams } from 'react-router-dom'

import { FeaturePanel } from '@/components/live-meeting/FeaturePanel'
import { LiveMeetingTopBar } from '@/components/live-meeting/LiveMeetingTopBar'
import { ZoomPanel } from '@/components/live-meeting/ZoomPanel'
import { CueCardOverlay } from '@/components/live-meeting/overlays/CueCardOverlay'
import { NoticeOverlay } from '@/components/live-meeting/overlays/NoticeOverlay'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { PageLoader } from '@/components/ui/PageLoader'
import { useAuth } from '@/hooks/useAuth'
import { useLiveState } from '@/hooks/useLiveState'
import { useSession } from '@/hooks/useSession'
import { useSocket } from '@/hooks/useSocket'
import { useSocketEvents } from '@/hooks/useSocketEvents'
import { useZoomSDK } from '@/hooks/useZoomSDK'
import { useLiveClassStore } from '@/stores/liveClassStore'

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
  const { status, errorMsg, joinMeeting, leaveMeeting } = useZoomSDK(
    rootRef,
    sessionId,
    user ?? null,
  )

  const [confirmingLeave, setConfirmingLeave] = useState(false)
  const reset = useLiveClassStore((s) => s.reset)
  const tick = useLiveClassStore((s) => s.tick)
  const activeQuestion = useLiveClassStore((s) => s.activeQuestion)

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

  const confirmLeave = async () => {
    setConfirmingLeave(false)
    await leaveMeeting()
    navigate('/dashboard')
  }

  if (isLoading) return <PageLoader />

  if (session && session.status !== 'LIVE' && !isInstructor) {
    const ended = session.status === 'ENDED' || session.status === 'CANCELLED'
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-[#1A1A2E] text-white">
        {!ended && (
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-white/20 border-t-white" />
        )}
        <div className="text-center">
          <p className="text-lg font-semibold">
            {ended
              ? 'This class has ended.'
              : 'Waiting for the host to start the class…'}
          </p>
          {!ended && (
            <p className="mt-1 text-sm text-white/60">
              You’ll join automatically the moment the host starts.
            </p>
          )}
        </div>
        <button
          onClick={() => navigate('/dashboard')}
          className="text-sm text-primary-light hover:underline"
        >
          Back to dashboard
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-black">
      <LiveMeetingTopBar
        session={session}
        onLeave={() => setConfirmingLeave(true)}
      />
      <div className="flex min-h-0 flex-1">
        <div className="relative flex flex-1">
          <ZoomPanel
            rootRef={rootRef}
            status={status}
            errorMsg={errorMsg}
            onJoin={joinMeeting}
            hasZoomMeeting={!!session?.zoomMeetingId}
          />
          <CueCardOverlay />
        </div>
        <FeaturePanel
          sessionId={sessionId}
          user={user}
          isInstructor={isInstructor}
          joinedAt={joinedAt.current}
        />
      </div>
      <NoticeOverlay />
      <ConfirmDialog
        open={confirmingLeave}
        title="Leave the class?"
        description="You can rejoin while the session is live."
        confirmLabel="Leave"
        onConfirm={confirmLeave}
        onCancel={() => setConfirmingLeave(false)}
      />
    </div>
  )
}
