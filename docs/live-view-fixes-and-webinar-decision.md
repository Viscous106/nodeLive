# Live-meeting view fixes + the Webinar decision

Working note for the live Zoom view polish pass (host/attendee video framing,
chrome cleanup, screen-share fitting) and the one item that needs a **business
decision**: whether to move attendee-facing classes onto a Zoom **Webinar**.

> These M1–M5 are an **ad-hoc UI-fix set for this pass** — they are NOT the
> project roadmap milestones in `milestones-live-meeting.md` (which go M1–M9).

## Status

| # | Goal | Status |
|---|------|--------|
| M1 | Fill the black space around the video (no top/bottom/side bars) | ✅ done |
| M2 | Attendees view-only (can't broadcast video/audio/share) | ⛔ **blocked — needs Webinar** |
| M3 | Remove the Zoom View / layout menu (top info strip) | ✅ done |
| M4 | Host sees only itself, not other attendees | ⛔ **blocked — needs Webinar** |
| M5 | Screen share renders correctly (not stretched/unreadable) | ✅ implemented — needs a real-share visual check |

Code: all framing/chrome/share logic lives in
`frontend/src/hooks/useZoomSDK.ts` + `frontend/src/styles/globals.css`.

- **M1** — the camera video is stretched to fill (`object-fit: fill` +
  `scaleX/scaleY`), the accepted "fill, no bars" trade-off.
- **M5** — a screen share is detected via the SDK's `Participant.sharerOn`
  flag; while a share is live the video switches to `object-fit: contain` (no
  stretch, so slides/code stay readable) and the fill transform is dropped.
  Needs a host to start a real share once and eyeball it after deploy (the
  share can't be driven from an automated browser).

## Why M2 + M4 need a Webinar (the proof)

In a regular Zoom **Meeting**, every participant is an equal: the embedded
Meeting SDK gives the host **no API** to stop another participant turning on
their camera, talking, or screen-sharing (no `stopUserVideo` / `stopUserShare`
exist in `@zoom/meetingsdk` v6.1.0), and a screen share overrides any pin. So
in meeting mode an attendee can always hijack the active view — M2 and M4 are
not achievable with code.

A Zoom **Webinar** is the supported product for this: attendees are **view-only**
by design and can only broadcast if the host promotes them to panelist.

### Official Zoom sources (for the manager)

- **Meeting and webinar comparison** — https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0062404
  - *"Only hosts and panelists can present, and attendees are view-only…"*
  - *"Only hosts and panelists can enable their videos."*
  - *"Only hosts and panelists can share their screens."*
  - *"Attendees join in listen-only mode."*
  - vs. Meetings: *"All participants can enable their videos / share their screens."*
- **Comparison by platform** — https://support.zoom.us/hc/en-us/articles/360027397692-Zoom-Meetings-and-Webinars-comparison-by-platform
- **Meeting SDK docs (roles)** — https://developers.zoom.us/docs/meeting-sdk/

> Note: the legacy `support.zoom.us/.../115005474943` link now 301-redirects to
> the `support.zoom.com` URL above (Zoom migrated its help-center domain).

## Decision needed

**Does the Zoom account have (or will it buy) a Webinar license?** It is a paid
add-on tied to the account plan.

- **Yes →** backend change: create a **webinar** instead of a meeting at
  session-create time (`backend/app/utils/zoom_meetings.py`), and the
  view-only / host-only-broadcast behaviour (M2 + M4) comes for free from the
  webinar role model — no frontend hacks.
- **No →** M2 + M4 stay out of scope; the class runs as a meeting where
  attendees can broadcast. M1/M3/M5 (framing + share fitting) still apply.
