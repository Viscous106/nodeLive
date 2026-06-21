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
  const [status, setStatus] = useState<ZoomStatus>('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const setAttendeeCount = useLiveClassStore((s) => s.setAttendeeCount)

  useEffect(() => {
    const client = ZoomMtgEmbedded.createClient()
    clientRef.current = client
    return () => {
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
    try {
      const { signature, sdkKey, zoomMeetingId, password, zak } =
        await api.post<ZoomJoin>(`/api/sessions/${sessionId}/join`)

      // Size the Zoom view to the actual panel so the video fills the space
      // instead of rendering at a fixed 1000×600 (leaving a black gap).
      const root = rootRef.current
      const viewW = Math.max(root.clientWidth || 0, 320)
      const viewH = Math.max(root.clientHeight || 0, 240)

      await clientRef.current.init({
        debug: false,
        zoomAppRoot: root,
        language: 'en-US',
        patchJsMedia: true,
        leaveOnPageUnload: true,
        customize: {
          video: {
            isResizable: true,
            // Ribbon is the ONLY Component-View layout that keeps the control
            // toolbar (mic / camera / share / leave). Gallery & Speaker render as
            // full-screen overlays that COVER the toolbar — which is why forcing
            // Gallery removed every control (and hover revealed nothing: there was
            // no toolbar to reveal). So we keep Ribbon and enlarge it to fill the
            // panel, anchored top-left and non-draggable → a big video WITH the
            // native controls. The view-switcher still lets users flip to Gallery.
            defaultViewType: 'ribbon' as SuspensionViewType,
            popper: { disableDraggable: true, anchorPosition: { top: 0, left: 0 } },
            viewSizes: {
              ribbon: { width: viewW, height: viewH },
              default: { width: viewW, height: viewH },
            },
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

      // Enforce Ribbon view (the layout that keeps the control toolbar). Zoom
      // can remember a previously-chosen view (e.g. our old Gallery default), so
      // re-assert Ribbon once connected, plus a few delayed retries (the view
      // isn't ready the instant join() resolves).
      const forceRibbon = () => {
        try {
          const r = c.setViewType?.('ribbon')
          // setViewType returns an ExecutedResult (may be a Promise) — swallow a
          // rejection if the view isn't ready; a later retry will succeed.
          if (r && typeof r.catch === 'function') r.catch(() => {})
        } catch {
          /* view not ready yet — a retry will catch it */
        }
      }
      c.on('connection-change', (p: { state?: string }) => {
        if (p?.state === 'Connected') forceRibbon()
      })
      forceRibbon()
      ;[400, 1200, 2500, 4000].forEach((ms) => window.setTimeout(forceRibbon, ms))

      refreshAttendees()
    } catch (err: unknown) {
      let msg: string
      if (err instanceof Error) {
        msg = err.message
      } else if (typeof err === 'object' && err !== null) {
        const e = err as Record<string, unknown>
        msg = `${e.type ?? ''} ${e.reason ?? ''} ${e.errorCode ?? ''}`.trim()
      } else {
        msg = String(err)
      }
      setErrorMsg(msg || 'Failed to join the meeting — check the console (F12).')
      setStatus('error')
    }
  }, [rootRef, sessionId, user, refreshAttendees])

  const leaveMeeting = useCallback(async () => {
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
