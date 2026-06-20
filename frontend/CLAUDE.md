# CLAUDE.md — frontend (linkHQ SPA)

React 19 + TypeScript + Vite 8 · Tailwind 4 + shadcn/ui · Zustand (client state) +
TanStack Query (server state) · socket.io-client · Zoom Meeting SDK v6.1.

## Commands (run from `frontend/`)
```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # tsc -b && vite build — ALSO the typecheck gate (CI)
```
There is no separate typecheck — `npm run build` is it.

## Conventions
- `src/lib/api.ts` is the fetch wrapper: `credentials: 'include'` (HttpOnly auth
  cookie), throws `ApiError` on non-2xx. The backend serializes **snake_case** —
  map to camelCase at the hook edge (see `src/hooks/useRecording.ts`).
- Server state via TanStack Query hooks in `src/hooks/`; live realtime state via
  Zustand (`src/stores/liveClassStore.ts`) fed by socket events.
- Routes in `src/router.tsx` — lazy-loaded, wrapped by `ProtectedRoute` /
  `AdminRoute`. The session detail route is `/session/:sessionId` (singular).

## Zoom SDK (critical)
- **COOP/COEP required** — `Cross-Origin-Opener-Policy: same-origin` +
  `Cross-Origin-Embedder-Policy: require-corp` in `vite.config.ts` (dev) and the
  backend middleware (bundled deploy). Without them the SDK fails to init.
- Under COEP, any cross-origin media/asset must be CORS-loaded: set
  `crossOrigin="anonymous"` AND the host must send `Access-Control-Allow-Origin`
  (plus Range support for video seeking). This is why the recording player uses
  `crossOrigin` and the demo MP4 is served from a CORS + CORP host.
- Join with `customerKey = user.id.slice(0, 35)` (the attendance identity bridge).

## Recording player (M7)
`src/pages/RecordingPlayerPage.tsx` (route `/session/:sessionId/recording`):
fetches a playback URL, plays via `<video crossOrigin="anonymous">`, and reports
**actually-played spans** on a ~10s heartbeat (not raw `currentTime`), so dragging
the scrubber to the end yields partial — not full — watch credit. Hooks live in
`src/hooks/useRecording.ts`. "Continue Watching" cards (`VideoCard`) link here.

## Live meeting
`src/pages/LiveMeetingPage.tsx` — split pane: `ZoomPanel` + `FeaturePanel`
(Chat/Quiz/Poll/Leaderboard/Bookmarks/Notes) + overlays. This is the heaviest
bundle (Zoom SDK); the `>500kB chunk` warning at build time is expected and not
an error.
