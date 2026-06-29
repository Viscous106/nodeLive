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

import { api } from '@/lib/api'
import { getSocket } from '@/lib/socket'
import { useLiveClassStore } from '@/stores/liveClassStore'
import type { User, ZoomJoin } from '@/types'

// CJS/ESM interop: the embedded SDK ships as a UMD bundle.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ZoomMtgEmbedded = ((ZoomSDK as any).default ?? ZoomSDK) as typeof import('@zoom/meetingsdk/embedded').default
type EmbeddedClient = ReturnType<typeof ZoomMtgEmbedded.createClient>

export type ZoomStatus = 'idle' | 'joining' | 'in-meeting' | 'error'

// Our custom top bar height (LiveMeetingTopBar, h-12).
const HEADER_H = 48
// Zoom's Component View widget = a FIXED-height meeting-info bar (~76px) on top +
// the video canvas + the control toolbar (#wc-footer) pinned to the widget's
// bottom. Those two bars are fixed pixel heights regardless of screen size, so
// the reliable way to guarantee the toolbar fits is to reserve a fixed slice for
// them and give the video the rest — which works out to ~80-85% of the height on
// a normal screen (big enough to not feel small, with room for the toolbar). The
// original bug sized the video to the FULL height, so the widget grew taller than
// its container and the toolbar overflowed off the bottom. correctToolbar() then
// measures the real toolbar and trims the video further only if anything still
// spills over — so even an unusually tall info-bar can't hide the controls.
const SDK_CHROME_BASELINE = 132

// Convergence tuning for the bidirectional toolbar loop (see correctToolbar).
// TARGET_GAP: desired px between the toolbar's bottom and the container's bottom
// once settled — small, so almost no black margin, but > 0 so the toolbar is
// provably on-screen. DEADBAND: ignore errors smaller than this to kill
// oscillation/jitter from sub-pixel rounding and the footer's .2s transition.
// MIN_VIDEO_H: never shrink the video below this.
const TARGET_GAP = 6
const DEADBAND = 3
const MIN_VIDEO_H = 240

export function useZoomSDK(
  rootRef: React.RefObject<HTMLDivElement | null>,
  sessionId: string,
  user: User | null,
) {
  const clientRef = useRef<EmbeddedClient | null>(null)
  const resizeObsRef = useRef<ResizeObserver | null>(null)
  const resizeListenerRef = useRef<(() => void) | null>(null)
  const settleTimersRef = useRef<ReturnType<typeof setTimeout>[]>([])
  const [status, setStatus] = useState<ZoomStatus>('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const setAttendeeCount = useLiveClassStore((s) => s.setAttendeeCount)

  useEffect(() => {
    const client = ZoomMtgEmbedded.createClient()
    clientRef.current = client
    return () => {
      settleTimersRef.current.forEach(clearTimeout)
      settleTimersRef.current = []
      resizeObsRef.current?.disconnect()
      resizeObsRef.current = null
      if (resizeListenerRef.current) {
        window.removeEventListener('resize', resizeListenerRef.current)
        resizeListenerRef.current = null
      }
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

      const root = rootRef.current
      // Initial size: window dimensions are reliable before the SDK mutates the
      // DOM. Reserve the header + SDK chrome so the widget (and its control
      // toolbar) fits inside the container from the first frame.
      const container = root.parentElement ?? root
      const initialSize = {
        width: Math.max(window.innerWidth, 320),
        height: Math.max(window.innerHeight - HEADER_H - SDK_CHROME_BASELINE, 240),
      }
      // Locate the SDK's bottom control toolbar (mic/camera/share/chat/leave).
      // Confirmed selector in SDK v6.1: <footer id="wc-footer"> with class
      // "footer main-footer". Fall back to walking up from a known control button
      // so a class rename can't silently break the measurement.
      const findToolbar = (): HTMLElement | null => {
        const r = rootRef.current
        if (!r) return null
        return (
          r.querySelector<HTMLElement>('#wc-footer') ??
          r.querySelector<HTMLElement>('.footer.main-footer') ??
          r.querySelector<HTMLElement>('.footer') ??
          r
            .querySelector<HTMLElement>(
              '.join-audio-container__btn, .send-video-container__btn',
            )
            ?.closest<HTMLElement>('footer, [class*="footer"]') ??
          null
        )
      }

      // Pre-join capability probe (read-only). checkSystemRequirements() returns
      // { audio, video, screen }: boolean. If screen capture is unsupported in
      // this environment, surface it instead of letting remote viewers receive a
      // silent black share frame (Issue #4). Does NOT grant entitlements.
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const compat = (clientRef.current as any).checkSystemRequirements?.()
        if (compat && compat.screen === false) {
          console.warn(
            '[zoom] Screen share is not supported in this environment ' +
              '(software encode / account restriction). Remote viewers may see ' +
              'a black frame.',
          )
        }
      } catch {
        /* probe is best-effort */
      }

      await clientRef.current.init({
        debug: false,
        zoomAppRoot: root,
        language: 'en-US',
        patchJsMedia: true,
        leaveOnPageUnload: true,
        customize: {
          video: {
            isResizable: false,
            popper: { disableDraggable: true, anchorPosition: { top: 0, left: 0 } },
            viewSizes: { default: initialSize, ribbon: initialSize },
            // Active-speaker view (single active video filling the area, no
            // participant ribbon) instead of gallery. SuspensionViewType is a
            // const enum — runtime value is the string 'active'.
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            defaultViewType: 'active' as any,
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
        zak: zak ?? '',
      })

      setStatus('in-meeting')

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const c = clientRef.current as any
      // Ensure active-speaker view after the meeting initialises. The
      // defaultViewType init option sets the initial view but some SDK versions
      // reset it after join(); calling setViewType explicitly guarantees it.
      try { c.setViewType?.('active') } catch { /* not ready yet */ }
      window.setTimeout(() => { try { c.setViewType?.('active') } catch { /* */ } }, 1500)
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

      // `videoH` is the height we ask the SDK to render the video at. It starts
      // from the container height minus a baseline chrome reserve, then
      // correctToolbar() trims it further if the real toolbar still overflows.
      let videoH = Math.max(
        (container.getBoundingClientRect().height ||
          window.innerHeight - HEADER_H) - SDK_CHROME_BASELINE,
        240,
      )

      // Push the current width + videoH to the SDK. Width tracks the container
      // so the video shrinks when the side panel opens.
      const applySize = () => {
        const rect = container.getBoundingClientRect()
        const w = Math.max(rect.width > 0 ? rect.width : window.innerWidth, 320)
        const sz = { width: w, height: Math.max(videoH, 240) }
        try {
          c.updateVideoOptions?.({ viewSizes: { default: sz, ribbon: sz } })
        } catch {
          /* not ready yet */
        }
      }

      // BIDIRECTIONAL convergent corrector. Measure the gap between the REAL
      // toolbar's bottom and the container's bottom:
      //   gap = container.bottom - toolbar.bottom
      // The toolbar is `position:absolute; bottom:0` of the SDK widget, and the
      // widget's height tracks videoH plus a fixed top info-bar — so moving
      // videoH by Δ moves the toolbar's bottom by ~Δ (loop gain ≈ 1). We steer
      // gap toward a small positive TARGET_GAP:
      //   - gap < 0  → toolbar overflows below the fold → shrink video.
      //   - gap > TARGET_GAP → wasted black margin below the toolbar → grow.
      //   - |gap - TARGET_GAP| <= DEADBAND → converged, do nothing.
      // The grow step is capped at (gap - TARGET_GAP) so that even if the gain
      // is under-estimated we can never push the toolbar past the bottom;
      // shrink fully clears any overflow plus the target. Reads actual rendered
      // geometry, so it assumes nothing about the chrome height.
      const correctToolbar = () => {
        const toolbar = findToolbar()
        if (!toolbar) return
        const cRect = container.getBoundingClientRect()
        const tRect = toolbar.getBoundingClientRect()
        if (tRect.height === 0 || cRect.height === 0) return // not laid out yet
        const gap = cRect.bottom - tRect.bottom
        const error = gap - TARGET_GAP // >0 too much margin, <0 overflowing
        if (Math.abs(error) <= DEADBAND) return // converged — avoid jitter
        const maxH = Math.max(cRect.height, MIN_VIDEO_H)
        let next: number
        if (error > 0) {
          // Excess gap: grow, but never by more than the gap above the target,
          // so the toolbar cannot cross the bottom even if the gain is < 1.
          next = Math.min(videoH + error, maxH)
        } else {
          // Overflow: shrink enough to pull the toolbar fully back in and seat
          // it at the target margin.
          next = Math.max(videoH + error, MIN_VIDEO_H)
        }
        if (Math.abs(next - videoH) < 1) return // no actionable change
        videoH = next
        applySize()
      }

      // Reset to a conservative baseline for the current container size (chrome
      // slightly OVER-reserved so the very first frame never hides the toolbar),
      // then fire a burst of measure-and-correct passes that converge UP or DOWN
      // to TARGET_GAP. The SDK re-renders async (and the footer has a .2s
      // transform transition), so we retry as it settles — extra late passes let
      // the loop reach the target instead of stopping at the first non-overflow.
      const settle = () => {
        videoH = Math.max(
          (container.getBoundingClientRect().height ||
            window.innerHeight - HEADER_H) - SDK_CHROME_BASELINE,
          MIN_VIDEO_H,
        )
        applySize()
        // Clear any pending burst before scheduling a new one so rapid resizes
        // (e.g. window drag) don't stack timers.
        settleTimersRef.current.forEach(clearTimeout)
        settleTimersRef.current = [
          120, 350, 700, 1100, 1600, 2200, 3000, 4000,
        ].map((ms) => window.setTimeout(correctToolbar, ms))
      }

      settle()
      c.on('connection-change', (p: { state?: string }) => {
        if (p?.state === 'Connected') settle()
      })

      // Re-settle when the container resizes (side panel open/close) or the
      // window resizes. The observer watches OUR flex container, whose size is
      // driven by layout — not by the SDK widget — so updateVideoOptions can't
      // feed back into it and loop.
      resizeObsRef.current?.disconnect()
      resizeObsRef.current = new ResizeObserver(() => settle())
      resizeObsRef.current.observe(container)

      if (resizeListenerRef.current) {
        window.removeEventListener('resize', resizeListenerRef.current)
      }
      resizeListenerRef.current = settle
      window.addEventListener('resize', settle)

      refreshAttendees()
    } catch (err: unknown) {
      let msg: string
      if (err instanceof Error && 'status' in err) {
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
    settleTimersRef.current.forEach(clearTimeout)
    settleTimersRef.current = []
    resizeObsRef.current?.disconnect()
    resizeObsRef.current = null
    if (resizeListenerRef.current) {
      window.removeEventListener('resize', resizeListenerRef.current)
      resizeListenerRef.current = null
    }
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
