import { useEffect, useRef } from 'react'

import { useNavigate, useParams } from 'react-router-dom'

import { FeaturePanel } from '@/components/live-meeting/FeaturePanel'
import { LiveMeetingTopBar } from '@/components/live-meeting/LiveMeetingTopBar'
import { ZoomPanel } from '@/components/live-meeting/ZoomPanel'
import { CueCardOverlay } from '@/components/live-meeting/overlays/CueCardOverlay'
import { NoticeOverlay } from '@/components/live-meeting/overlays/NoticeOverlay'
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

  const leave = async () => {
    if (!window.confirm('Leave the class?')) return
    await leaveMeeting()
    navigate('/dashboard')
  }

  if (isLoading) return <PageLoader />

  if (session && session.status !== 'LIVE' && !isInstructor) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-[#1A1A2E] text-white">
        <p className="text-lg font-semibold">This session isn’t live right now.</p>
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
      <LiveMeetingTopBar session={session} onLeave={leave} />
      <div className="flex min-h-0 flex-1">
        <div className="relative flex flex-1">
          <ZoomPanel
            rootRef={rootRef}
            status={status}
            errorMsg={errorMsg}
            onJoin={joinMeeting}
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
    </div>
  )
}
