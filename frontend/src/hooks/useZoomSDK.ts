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
// Reserve space for the SDK's stacked info-bar + control toolbar; correct()
// then grows the video to fill the remaining height with the toolbar still
// on-screen. (Overlaying the bars on the video to remove this reserve made the
// SDK's auto-sizing unstable, so we keep them in normal flow.)
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
      // Height-bound the very first frame too (width clamped so a 16:9 video
      // can't start taller than the area), so the toolbar isn't hidden before
      // settle()/correct() take over.
      const initH = Math.max(
        window.innerHeight - HEADER_H - SDK_CHROME_BASELINE,
        240,
      )
      const initialSize = {
        width: Math.max(Math.min(window.innerWidth, Math.round((initH * 16) / 9)), 320),
        height: initH,
      }
      // Locate the SDK's bottom control toolbar (mic/camera/share/chat/leave).
      // Confirmed selector in SDK v6.1: <footer id="wc-footer"> with class
      // "footer main-footer". Fall back to walking up from a known control button
      // so a class rename can't silently break the measurement.
      const findToolbar = (): HTMLElement | null => {
        const r = rootRef.current
        if (!r) return null
        // Older SDK builds expose a stable footer id/class.
        const known =
          r.querySelector<HTMLElement>('#wc-footer') ??
          r.querySelector<HTMLElement>('.footer.main-footer') ??
          r.querySelector<HTMLElement>('.footer')
        if (known) return known
        // This SDK build renders the controls as a MUI bar with only hashed class
        // names, so locate it by SHAPE: a control button near the bottom, then
        // climb to the wide, short bar that holds it. This only MEASURES the bar
        // (so correct() can grow the video to fill the slack above it) — it never
        // hides or moves it, so it can't affect audio/video join.
        const box = (r.parentElement ?? r).getBoundingClientRect()
        const btn = Array.from(r.querySelectorAll<HTMLElement>('button')).find(
          (b) => {
            const rect = b.getBoundingClientRect()
            return rect.height > 0 && rect.top > box.bottom - 140
          },
        )
        let bar: HTMLElement | null = btn ?? null
        for (let i = 0; i < 7 && bar; i++) {
          const rect = bar.getBoundingClientRect()
          if (rect.width > 700 && rect.height < 90) return bar
          bar = bar.parentElement
        }
        return null
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

      // Sizing model: WIDTH is the lever, not height.
      //
      // The SDK sizes its video/share canvas to FILL the width we give it and
      // derives the height from the content's aspect ratio. So a full-width 16:9
      // video on a wide, short area becomes TALLER than the container — the
      // control toolbar (#wc-footer, pinned to the widget's bottom) is pushed
      // below the fold and clipped (host loses the controls) and the video is
      // vertically cropped (students see "half the presenter"). Shrinking the
      // height we request does nothing because the height is width-derived.
      //
      // Instead we shrink the canvas WIDTH until the content's height fits, which
      // letterboxes it (whole presenter, thin black bars) and keeps the toolbar
      // on-screen. `curW` is the width we push; correct() measures the REAL
      // toolbar and trims curW further for ANY content aspect — so an odd-ratio
      // screen share converges too, without assuming a ratio.
      let curW = 0

      // The SDK pins its widget `position:absolute; left:0; top:0` inside the
      // mount, so a letterboxed (narrower-than-container) canvas sits flush left
      // with ALL the black margin dumped on the right. We centre it by nudging
      // the widget's own left/top — measured against the container, because the
      // widget's offsetParent is a zero-width wrapper (so `left:50%` is useless;
      // the popper anchor doesn't move the widget box either).
      const findWidget = (): HTMLElement | null => {
        const r = rootRef.current
        if (!r) return null
        return (
          Array.from(r.querySelectorAll<HTMLElement>('div')).find((d) => {
            const cs = getComputedStyle(d)
            const rect = d.getBoundingClientRect()
            return (
              cs.position === 'absolute' && rect.width > 400 && rect.height > 300
            )
          }) ?? null
        )
      }

      const center = () => {
        const widget = findWidget()
        if (!widget) return
        const cRect = container.getBoundingClientRect()
        if (cRect.width === 0) return
        // Measure with NO transform so the position + stretch ratio are correct.
        widget.style.transform = 'none'
        const wRect = widget.getBoundingClientRect()
        const naturalW = widget.offsetWidth
        if (naturalW < 100) return
        const curLeft = parseFloat(widget.style.left) || 0
        const curTop = parseFloat(widget.style.top) || 0
        const desiredX = Math.max((cRect.width - naturalW) / 2, 0)
        const desiredY = Math.max((cRect.height - wRect.height) / 2, 0)
        const nl = Math.round(curLeft + (desiredX - (wRect.left - cRect.left)))
        const nt = Math.round(curTop + (desiredY - (wRect.top - cRect.top)))
        widget.style.right = 'auto'
        widget.style.bottom = 'auto'
        widget.style.left = nl + 'px'
        widget.style.top = nt + 'px'
        // STRETCH horizontally to fill the full width — removes the side bars.
        // The 16:9 feed gets widened, so the presenter looks a bit stretched:
        // the deliberate "fill, no black bars" trade-off. Vertical is untouched,
        // and a CSS transform keeps the controls in the DOM + clickable.
        const ratio = Math.max(cRect.width / naturalW, 1)
        widget.style.transformOrigin = 'center top'
        widget.style.transform = `scaleX(${ratio})`
      }

      const apply = () => {
        const rect = container.getBoundingClientRect()
        const cw = Math.max(rect.width > 0 ? rect.width : window.innerWidth, 320)
        const ch = Math.max(
          rect.height > 0 ? rect.height : window.innerHeight - HEADER_H,
          320,
        )
        const availH = Math.max(ch - SDK_CHROME_BASELINE, MIN_VIDEO_H)
        if (curW <= 0) curW = Math.min(cw, Math.round((availH * 16) / 9))
        curW = Math.max(Math.min(curW, cw), 320)
        const sz = { width: curW, height: availH }
        try {
          c.updateVideoOptions?.({ viewSizes: { default: sz, ribbon: sz } })
        } catch {
          /* not ready yet */
        }
        center()
      }

      // Measure the REAL toolbar and steer curW so its bottom sits a small
      // TARGET_GAP above the container's bottom. The widget height scales ~linearly
      // with the canvas width (height = width / aspect), so we rescale curW by
      // (fittedHeight / currentHeight). Reads rendered geometry, so it assumes
      // nothing about the content ratio — camera or screen share both converge.
      const correct = () => {
        const toolbar = findToolbar()
        if (!toolbar) return
        const cRect = container.getBoundingClientRect()
        const tRect = toolbar.getBoundingClientRect()
        if (tRect.height === 0 || cRect.height === 0) return // not laid out yet
        const widgetH = tRect.bottom - cRect.top // mount top → toolbar bottom
        if (widgetH <= 0) return
        const delta = tRect.bottom - (cRect.bottom - TARGET_GAP) // >0 overflow
        if (Math.abs(delta) <= DEADBAND) return // converged — avoid jitter
        const cw = Math.max(cRect.width, 320)
        // Shrink (delta>0) or grow (delta<0) width in proportion to the height
        // change needed; growth is capped at the container width.
        let next = (curW * (widgetH - delta)) / widgetH
        next = Math.max(320, Math.min(next, cw))
        if (Math.abs(next - curW) < 1) return // no actionable change
        curW = next
        apply()
      }

      // Reset to a fresh 16:9 guess for the current container, then fire a burst
      // of measure-and-correct passes (the SDK re-renders async + the footer has
      // a .2s transition) that converge for whatever is actually on screen.
      const settle = () => {
        const rect = container.getBoundingClientRect()
        const ch = Math.max(
          rect.height > 0 ? rect.height : window.innerHeight - HEADER_H,
          320,
        )
        const availH = Math.max(ch - SDK_CHROME_BASELINE, MIN_VIDEO_H)
        const cw = Math.max(rect.width > 0 ? rect.width : window.innerWidth, 320)
        curW = Math.min(cw, Math.round((availH * 16) / 9))
        apply()
        // Clear any pending burst before scheduling a new one so rapid resizes
        // (e.g. window drag) don't stack timers.
        settleTimersRef.current.forEach(clearTimeout)
        settleTimersRef.current = [
          120, 350, 700, 1100, 1600, 2200, 3000, 4000,
        ].map((ms) =>
          window.setTimeout(() => {
            correct()
            center()
          }, ms),
        )
      }

      settle()
      c.on('connection-change', (p: { state?: string }) => {
        if (p?.state === 'Connected') settle()
      })
      // A screen share starting/stopping swaps the active canvas to a different
      // aspect ratio — re-fit so the share isn't cropped and the toolbar stays
      // visible.
      c.on('peer-share-state-change', () => settle())
      // The active-speaker tile (and camera on/off) re-renders the widget, which
      // resets its position — re-fit + re-centre so it doesn't snap back to the
      // top-left.
      c.on('active-speaker', () => settle())

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
