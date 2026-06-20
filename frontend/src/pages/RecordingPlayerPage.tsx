import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useHeartbeat, useRecordingProgress, useRecordingUrl } from '@/hooks/useRecording'
import { ApiError } from '@/lib/api'

const HEARTBEAT_MS = 10_000

export default function RecordingPlayerPage() {
  const { sessionId = '' } = useParams()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [percent, setPercent] = useState(0)

  const urlQ = useRecordingUrl(sessionId)
  const progressQ = useRecordingProgress(sessionId)
  const heartbeat = useHeartbeat(sessionId)

  // span tracking — exactly the prototype's contiguous-play logic
  const spanStart = useRef<number | null>(null)
  const lastTime = useRef(0)
  const resumeAt = progressQ.data?.lastPositionSecs ?? 0

  useEffect(() => {
    if (progressQ.data) setPercent(progressQ.data.percentComplete)
  }, [progressQ.data])

  const flush = useCallback(
    (reason: string) => {
      const v = videoRef.current
      if (!v || spanStart.current == null) return
      const from = spanStart.current
      const to = lastTime.current
      spanStart.current = v.paused ? null : v.currentTime
      if (to - from < 0.5) return
      heartbeat.mutate(
        { playedFrom: from, playedTo: to, duration: v.duration || 0 },
        { onSuccess: (p) => setPercent(p.percentComplete) },
      )
      void reason
    },
    [heartbeat],
  )

  useEffect(() => {
    const id = setInterval(() => flush('interval'), HEARTBEAT_MS)
    const onUnload = () => flush('unload')
    window.addEventListener('pagehide', onUnload)
    return () => {
      clearInterval(id)
      window.removeEventListener('pagehide', onUnload)
      flush('unmount')
    }
  }, [flush])

  const onLoadedMetadata = () => {
    if (resumeAt > 0 && videoRef.current) videoRef.current.currentTime = resumeAt
  }
  const onPlay = () => {
    if (videoRef.current) spanStart.current = videoRef.current.currentTime
  }
  const onTimeUpdate = () => {
    if (videoRef.current && !videoRef.current.seeking)
      lastTime.current = videoRef.current.currentTime
  }
  const onSeeking = () => flush('seek')
  const onSeeked = () => {
    if (videoRef.current && !videoRef.current.paused)
      spanStart.current = videoRef.current.currentTime
  }
  const onPause = () => flush('pause')
  const onEnded = () => flush('ended')

  const notAvailable = urlQ.error instanceof ApiError && urlQ.error.status === 404
  const notConfigured = urlQ.error instanceof ApiError && urlQ.error.status === 501

  return (
    <div className="mx-auto max-w-4xl p-6">
      <Link to={`/session/${sessionId}`} className="text-sm text-text-link">
        ← Back to session
      </Link>
      <h1 className="mt-2 text-xl font-semibold text-text-primary">
        Recording — {(percent * 100).toFixed(1)}% watched
      </h1>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-border">
        <div
          className="h-full bg-text-link transition-[width]"
          style={{ width: `${Math.min(100, percent * 100)}%` }}
        />
      </div>

      <div className="mt-4">
        {urlQ.isLoading && <p className="text-text-muted">Loading recording…</p>}
        {notAvailable && (
          <p className="text-text-muted">
            No recording is available for this session yet.
          </p>
        )}
        {notConfigured && (
          <p className="text-text-muted">
            Recording playback is not configured on this server.
          </p>
        )}
        {urlQ.data && (
          <video
            ref={videoRef}
            src={urlQ.data.url}
            controls
            crossOrigin="anonymous"
            className="w-full rounded-card bg-black"
            onLoadedMetadata={onLoadedMetadata}
            onPlay={onPlay}
            onTimeUpdate={onTimeUpdate}
            onSeeking={onSeeking}
            onSeeked={onSeeked}
            onPause={onPause}
            onEnded={onEnded}
          />
        )}
      </div>
    </div>
  )
}
