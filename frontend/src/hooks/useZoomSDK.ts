/**
 * All Zoom Meeting SDK (Component View) logic, ported from testing/src/App.tsx
 * with the production fixes from plan.md Appendix D:
 *   - createClient once (ref), destroyClient on unmount
 *   - patchJsMedia + leaveOnPageUnload in init()
 *   - sdkKey + customerKey passed to join() (identity glue for webhooks)
 *
 * The signature is minted server-side by POST /api/sessions/:id/join, which
 * encodes the host/attendee role — the client never picks its own role.
 *
 * Attendee count and captions are SDK-driven and UI-only: the count feeds the
 * top bar, captions are forwarded to the socket for the AI buffer (M5). Neither
 * is the durable attendance record (that's webhooks, M6).
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import * as ZoomSDK from '@zoom/meetingsdk/embedded'
import type { SuspensionViewType } from '@zoom/meetingsdk/embedded'

import { api } from '@/lib/api'
import { getSocket } from '@/lib/socket'
import { useLiveClassStore } from '@/stores/liveClassStore'
import type { User, ZoomJoin } from '@/types'

// CJS/ESM interop: the embedded SDK ships as a UMD bundle.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ZoomMtgEmbedded = ((ZoomSDK as any).default ?? ZoomSDK) as typeof import('@zoom/meetingsdk/embedded').default
type EmbeddedClient = ReturnType<typeof ZoomMtgEmbedded.createClient>

export type ZoomStatus = 'idle' | 'joining' | 'in-meeting' | 'error'

export function useZoomSDK(
  rootRef: React.RefObject<HTMLDivElement | null>,
  sessionId: string,
  user: User | null,
) {
  const clientRef = useRef<EmbeddedClient | null>(null)
  const resizeObsRef = useRef<ResizeObserver | null>(null)
  const [status, setStatus] = useState<ZoomStatus>('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const setAttendeeCount = useLiveClassStore((s) => s.setAttendeeCount)

  useEffect(() => {
    const client = ZoomMtgEmbedded.createClient()
    clientRef.current = client
    return () => {
      resizeObsRef.current?.disconnect()
      resizeObsRef.current = null
      try {
        ZoomMtgEmbedded.destroyClient()
      } catch {
        /* noop */
      }
      clientRef.current = null
    }
  }, [])

  const refreshAttendees = useCallback(() => {
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const list = (clientRef.current as any)?.getAttendeeslist?.() ?? []
      setAttendeeCount(Array.isArray(list) ? list.length : 0)
    } catch {
      /* not in a meeting yet */
    }
  }, [setAttendeeCount])

  const joinMeeting = useCallback(async () => {
    if (!clientRef.current || !rootRef.current || !user) return
    setStatus('joining')
    setErrorMsg('')
    // Known Zoom SDK error codes → friendly messages
    const ZOOM_ERROR_MESSAGES: Record<string, string> = {
      '3707': 'Meeting not found — the meeting ID may be invalid or the meeting has ended.',
      '3011': 'Incorrect meeting password.',
      '3000': 'Zoom SDK failed to initialize. Try refreshing the page.',
      '1': 'Meeting has not started yet.',
      '3001': 'Meeting has ended.',
      '200': 'Your Zoom credentials do not have permission to join this meeting.',
    }

    try {
      const { signature, sdkKey, zoomMeetingId, password, zak } =
        await api.post<ZoomJoin>(`/api/sessions/${sessionId}/join`)

      // Size the Zoom view to the actual panel. The Component View renders a
      // FIXED-pixel suspension window — it never reflows itself — so we measure
      // the panel now and keep it in sync with a ResizeObserver (below). Without
      // that, any viewport change after join (e.g. opening DevTools, resizing)
      // leaves the window at its old, oversized height and it overflows the
      // panel, forcing a scroll to reach the toolbar.
      const root = rootRef.current
      // Zoom renders its control toolbar (mic / camera / share / leave) BELOW the
      // video area. If we size the video to the full panel height, video+toolbar
      // overflows the panel bottom and the toolbar is clipped (the page is
      // overflow-hidden) — making the controls unreachable. Reserve the toolbar's
      // height so it lands inside the panel.
      const TOOLBAR_H = 56
      const panelSize = () => ({
        width: Math.max(Math.floor(root.getBoundingClientRect().width), 320),
        height: Math.max(
          Math.floor(root.getBoundingClientRect().height) - TOOLBAR_H,
          240,
        ),
      })
      const initialSize = panelSize()

      await clientRef.current.init({
        debug: false,
        zoomAppRoot: root,
        language: 'en-US',
        patchJsMedia: true,
        leaveOnPageUnload: true,
        customize: {
          video: {
            isResizable: true,
            // Default to Speaker view (large active speaker). The control toolbar
            // (mic / camera / share / leave) is kept reachable by (a) reserving
            // the footer's height in panelSize so it isn't clipped, and (b) a CSS
            // rule (globals.css) that forces Zoom's `.footer` visible in every
            // layout. Anchor top-left + non-draggable so the window fills the
            // panel instead of floating at a fixed offset.
            defaultViewType: 'speaker' as SuspensionViewType,
            popper: { disableDraggable: true, anchorPosition: { top: 0, left: 0 } },
            viewSizes: { default: initialSize, ribbon: initialSize },
          },
          meetingInfo: ['topic', 'host', 'mn', 'participant'],
        },
      })

      await clientRef.current.join({
        signature,
        sdkKey,
        meetingNumber: zoomMeetingId,
        password: password ?? '',
        userName: user.displayName,
        userEmail: user.email,
        customerKey: user.id.slice(0, 35),
        zak: zak ?? '', // host token → instructor can START the meeting
      })

      setStatus('in-meeting')

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const c = clientRef.current as any
      c.on('user-added', refreshAttendees)
      c.on('user-removed', refreshAttendees)
      c.on('user-updated', refreshAttendees)
      c.on('caption-message', (payload: { text?: string }) => {
        if (payload?.text) {
          getSocket().emit('caption_received', {
            sessionId,
            text: payload.text,
            timestamp: Date.now(),
          })
        }
      })

      // Default to Speaker view. Zoom can remember a prior view, so re-assert it
      // once connected plus a few delayed retries (the view isn't ready the
      // instant join() resolves). After these initial retries the user is free to
      // switch layouts — the footer stays visible in all of them.
      const forceSpeaker = () => {
        try {
          const r = c.setViewType?.('speaker')
          if (r && typeof r.catch === 'function') r.catch(() => {})
        } catch {
          /* view not ready yet — a retry will catch it */
        }
      }
      // Keep the fixed-size Zoom window matched to the panel. The Component View
      // doesn't reflow on its own, so re-apply viewSizes whenever the panel
      // changes size — this is what stops the window overflowing and forcing a
      // scroll to reach the toolbar.
      const applySize = () => {
        const sz = panelSize()
        try {
          c.updateVideoOptions?.({ viewSizes: { default: sz, ribbon: sz } })
        } catch {
          /* not ready yet */
        }
      }
      c.on('connection-change', (p: { state?: string }) => {
        if (p?.state === 'Connected') {
          forceSpeaker()
          applySize()
        }
      })
      forceSpeaker()
      ;[400, 1200, 2500, 4000].forEach((ms) =>
        window.setTimeout(() => {
          forceSpeaker()
          applySize()
        }, ms),
      )

      resizeObsRef.current?.disconnect()
      resizeObsRef.current = new ResizeObserver(() => applySize())
      resizeObsRef.current.observe(root)

      refreshAttendees()
    } catch (err: unknown) {
      let msg: string
      if (err instanceof Error && 'status' in err) {
        // ApiError from the server
        const httpStatus = (err as { status: number }).status
        if (httpStatus === 409) {
          msg = 'No Zoom meeting has been configured for this session.'
        } else if (httpStatus === 503) {
          msg = 'Meeting video is not available in this environment.'
        } else {
          msg = err.message
        }
      } else if (err instanceof Error) {
        msg = err.message
      } else if (typeof err === 'object' && err !== null) {
        const e = err as Record<string, unknown>
        const errorCode = e.errorCode
        msg =
          ZOOM_ERROR_MESSAGES[String(errorCode)] ??
          `${e.type ?? ''} ${e.reason ?? ''} ${errorCode ?? ''}`.trim()
      } else {
        msg = String(err)
      }
      setErrorMsg(msg || 'Failed to join the meeting — check the console (F12).')
      setStatus('error')
    }
  }, [rootRef, sessionId, user, refreshAttendees])

  const leaveMeeting = useCallback(async () => {
    resizeObsRef.current?.disconnect()
    resizeObsRef.current = null
    try {
      await clientRef.current?.leaveMeeting()
    } catch {
      /* noop */
    }
    setAttendeeCount(0)
    setStatus('idle')
  }, [setAttendeeCount])

  return { status, errorMsg, joinMeeting, leaveMeeting }
}
