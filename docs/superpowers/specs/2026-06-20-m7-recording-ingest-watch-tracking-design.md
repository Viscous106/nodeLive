# M7 — Recording Ingest + Watch-Tracking — Design

**Milestone:** M7 (Dev B · `feat/live-meeting`) · _compliance (Phase 3)_
**Date:** 2026-06-20
**Status:** Approved design → implementation
**Depends on:** M6 (`meetings` / `attendance_*` / webhook spine), `intervals.py`, `zoom_auth.py`, real `get_current_user`.

---

## 1. Goal & scope

Close the third compliance layer for *recordings*: a class recording lands in
object storage, students watch it, and watch credit is computed from the **union
of actually-played spans** (seeking to the end yields partial, not 100%). The
watch-% read-model is consumed by Dev A's dashboard ("Continue Watching").

**In scope (this PR):**
1. Recording ingest: `recording.completed` webhook → Celery job → download MP4 →
   stream to Cloudflare R2 → mark the meeting. Real Zoom path, **seam-tested like
   M6** (live path ported verbatim, raises until creds set).
2. Watch-tracking API (session-scoped): presigned playback URL, progress/resume,
   heartbeat (interval union), watch-status read-model.
3. A self-contained frontend `RecordingPlayer` route so the feature is provably
   working end-to-end. Flagged as Dev A's seam to relocate into the dashboard.
4. Tests (pytest + `npm run build`) and a real R2 end-to-end verification.

**Out of scope:** post-meeting AI (M8), analytics (M9), production hardening (MP).
Manual instructor upload is **not** built (decision: Zoom path only, seam-tested).

**Storage decision:** Cloudflare R2 via **boto3** S3-compatible client. Playback
uses **S3 presigned GET URLs** (portable across R2 and AWS S3), not the prototype's
AWS-only CloudFront signer. Returns **501** when R2 is unconfigured (by design).

---

## 2. Identity → entity mapping (explicit resolution rule)

```
ClassSession.zoom_meeting_id (numeric, e.g. "82912345678")
   └─► Meeting.zoom_meeting_id (numeric)        ─┐ one numeric id may map to
       Meeting.zoom_uuid (per-occurrence) ◄──────┘ MANY occurrences (recurring)
           └─► recording_s3_key + watch_progress
```

**Session → recording resolution rule (written, not incidental):** given a
`ClassSession`, select the `Meeting` rows whose `zoom_meeting_id` equals the
session's `zoom_meeting_id`, filter to `recording_status == 'stored'`, and pick
the one with the **most recent `ended_at`** (NULLs last). That `zoom_uuid` is the
recording served and the key for watch progress. If none, the recording is "not
available" (404).

**Watch identity is real:** `user.id` from `get_current_user` (cookie JWT). Unlike
attendance, there is no server-side truth for "what was watched" — see §7.

---

## 3. Data model (migration on top of M6's `meetings`)

**Alter `meetings`** (add columns; nullable, safe expand):
- `recording_s3_key: str | None`
- `recording_status: str` — `none | pending | stored | failed`, default `none`
- `recording_duration_secs: int | None` — **server-authoritative** duration
  (from Zoom `recording_files[].recording_end - recording_start`, or the file's
  duration metadata). Used by the heartbeat in preference to client-reported.

**New table `watch_progress`:**
| column | type | notes |
|---|---|---|
| `id` | str(36) PK | uuid |
| `zoom_uuid` | str(255) index | the resolved recording occurrence |
| `user_id` | str(36) | real app user id (`get_current_user`) |
| `last_position_secs` | float | resume point (= last `played_to`) |
| `max_position_secs` | float | furthest reached (audit) |
| `watched_segments` | JSON | merged `[[start,end],…]` (epoch-free, seconds) |
| `duration_secs` | float | recording length used for the %; server-auth preferred |
| `percent_complete` | float | `coverage_fraction(segments, duration)` ∈ [0,1] |
| `updated_at` | datetime | |

Unique constraint `(zoom_uuid, user_id)`. Migration: new Alembic revision after
`b8e3d6f1c742` (M6).

---

## 4. Recording ingest (Celery, seam-tested)

**4a. Webhook** (`app/api/webhooks.py`, extend `_handle_event`):
- New branch `recording.completed`:
  - `obj.uuid` → upsert `Meeting`, set `recording_status = 'pending'`.
  - Enqueue `recording_tasks.schedule_ingest(zoom_uuid, download_token, recording_files)`.
  - The webhook carries a short-lived `download_token` (object-level) — pass it
    through; the job prefers it and falls back to S2S OAuth.
- HMAC/raw-body/idempotency path is unchanged (already in M6).

**4b. Storage helper** (`app/utils/recording_storage.py`):
- `pick_mp4(recording_files)` — prefer `shared_screen_with_speaker_view`, else any MP4 (port of `pickMp4`).
- `_r2_client()` — boto3 client built from `R2_*` settings; raises if unset.
- `upload_stream(key, body_iter, content_type)` — multipart streaming upload to R2.
- `presign_get(key, ttl_secs)` — S3 presigned GET URL. Raises if R2 unconfigured.
- `is_configured()` — bool for the 501 gate.

**4c. Celery task** (`app/workers/recording_tasks.py`) — mirrors `attendance_tasks.py`:
- Pure `run_ingest(uuid, download_token, recording_files, *, get_token, http_get_stream, upload, mark)` with **injection seams** so it is fully unit-tested offline.
- Live wiring: download URL + `?access_token=` (prefer `download_token`, else
  `get_zoom_access_token()`); stream `httpx` response → `upload_stream` → `mark(uuid, key, 'stored', duration)`.
- On no-MP4 or download failure → `mark(uuid, None, 'failed')` and raise.
- `schedule_ingest(...)` enqueues via `.apply_async`.
- The live Zoom download path is **ported verbatim but not exercised in CI**
  (needs paid Zoom cloud recording + S2S) — exactly M6's posture.

---

## 5. Watch-tracking API — `app/api/recordings.py` (session-scoped)

All routes `Depends(get_current_user)` + session membership (reuse live.py's
`_member_session` dependency pattern).

- **`GET /api/sessions/{id}/recording/url`**
  → resolve recording (§2). `404` if no stored recording; `501` if R2
  unconfigured; else `{ url, expiresInSecs }` (presigned, ~300s TTL).
- **`GET /api/sessions/{id}/recording/progress`**
  → `{ lastPositionSecs, percentComplete, segments }` for this user (zeros if none).
- **`POST /api/sessions/{id}/recording/heartbeat`** `{ playedFrom, playedTo, duration }`
  → pure `apply_heartbeat(prev_segments, played_from, played_to, server_duration)`:
  - **clamp** `played_from/played_to` to `[0, duration]`;
  - union `prev + [from,to]` via **`merge_intervals`** (reuse `intervals.py`, no dup);
  - `percent = coverage_fraction(merged, duration)`;
  - `duration` = **server-authoritative** `recording_duration_secs` when set, else
    the client-reported `duration` (fallback only).
  - Upsert `watch_progress` (`max_position_secs = max(prev, played_to)`).
  → `{ percentComplete, segments }`.
- **`GET /api/sessions/{id}/recording/watch-status`** — the **read-model seam** for
  Dev A: `{ available: bool, percentComplete: float, lastPositionSecs: float,
  durationSecs: float | null }`. Shaped for `VideoCard`/`ContinueWatchingSection`
  (progress bar + Resume). `ClassSession` is unchanged.

---

## 6. Frontend player (provably-working seam)

`frontend/src/pages/RecordingPlayerPage.tsx` at route **`/session/:id/recording`**
(singular, matching the existing `/session/:id` detail route):
- Fetch `…/recording/url` (handle 404 "not available" + 501 "playback not configured").
- `<video crossorigin="anonymous" controls>` — `crossorigin` is **required** under
  COEP (see §8).
- On `loadedmetadata`: seek to `progress.lastPositionSecs` (resume).
- **Played-span detection (the client half of the compliance guarantee — port
  `testing/RecordingPlayer.tsx` faithfully, do NOT simplify):** track `lastTime`;
  on `timeupdate`, if `currentTime` advanced *contiguously* from `lastTime` (delta
  within a small epsilon of real elapsed), accumulate the span `[lastTime,
  currentTime]`; on `seeking`/discontinuity, **close** the current span and start
  a new one at the new position. Never log `[0, currentTime]`. Flush a heartbeat
  every ~10s of accumulated playback and on `pause`/`unload`.
- Show live watch % from the heartbeat response.
- Reuse the app's `api` client (cookie auth) + TanStack Query.

This route is self-contained; Dev A relocates it into the dashboard later and
wires `VideoCard` "Resume" → this route + `watch-status` for the progress bar.

---

## 7. Known issues / integrity notes (recorded, not hidden — M5/M6 style)

- **Watch-tracking is inherently client-reported.** There is no server-side source
  of truth for what was watched (unlike attendance's webhook + Reports API). The
  interval union defeats *casual* inflation (an honest player seeking to the end
  ≠ 100%), but a crafted client POSTing `{playedFrom:0, playedTo:duration}` still
  scores 100%. The compliance value is "honest viewing is measured honestly," not
  "tamper-proof." Documented here; hardening (signed heartbeats / server-sampled
  challenges) is out of scope.
- **Recurring meetings:** the §2 resolution rule picks the latest stored
  occurrence; multi-occurrence-per-session UX is not addressed.
- **Live Zoom download path** is ported verbatim but unexercised in CI (needs paid
  Zoom cloud recording + S2S OAuth) — same posture as M6's Reports-API fetch.

---

## 8. Deployment correctness — the "works in prod, not just local" checklist

This is where M7 breaks if the design ignores it. The live SDK forces
`Cross-Origin-Embedder-Policy: require-corp` app-wide; a cross-origin `<video>`
from R2 must satisfy COEP **and** support HTTP Range, or seeking (the whole point)
silently breaks.

1. **R2 bucket CORS** must allow the app origin, allow the **`Range`** request
   header, and **expose** `Content-Range`, `Accept-Ranges`, `Content-Length`.
   (Documented in the PR + `.env.example`; applied to the R2 bucket at deploy.)
2. **`<video crossorigin="anonymous">`** so the cross-origin media is CORS-loaded
   under COEP (otherwise COEP blocks it).
3. **Range support:** presigned S3/R2 GET URLs pass through `Range` natively — do
   **not** proxy the bytes through FastAPI (that would lose Range + defeat the CDN).
   Verify seeking works against real R2, not just play-from-start.
4. **COEP header parity:** the player route inherits vite's COOP/COEP in dev; the
   **production nginx/Railway proxy must replicate** COOP/COEP (already an MP item
   — called out here so M7's player isn't the thing that exposes the gap).
5. **New env** (`backend/.env.example` + `config.py`): `R2_ACCOUNT_ID`,
   `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_ENDPOINT_URL`
   (`https://<acct>.r2.cloudflarestorage.com`), `RECORDING_URL_TTL_SECS` (300).
   All empty by default → ingest + presign raise/501 (graceful degrade).

---

## 9. Tests & verification

**pytest (offline, CI-green):**
- `apply_heartbeat`: union of spans; **seek-to-end yields partial, not 100%**;
  clamping; server-duration preference over client.
- Ingest seams: `pick_mp4` selection; `download_token` preferred over S2S;
  status transitions `pending→stored` and `→failed` on no-MP4/download error.
- API: presign returns `501` when unconfigured; `404` when no stored recording;
  read-model shape; membership gating.
- `recording_storage.is_configured()` gate.
- (Reuse `intervals.py` tests — do not duplicate the primitive.)

**Frontend:** `npm run build` (tsc + vite) green.

**Real end-to-end (the anti-dummy gate, needs your R2 creds at verify time):**
1. Provision R2 bucket + token; set `R2_*` in `.env`; apply bucket CORS (§8.1).
2. Seed the bucket with a real MP4 and point a `Meeting.recording_s3_key` at it
   (`recording_status='stored'`, set `recording_duration_secs`); link a
   `ClassSession.zoom_meeting_id` to that meeting.
3. Open `/session/:id/recording`: confirm presigned playback loads, **seeking
   works** (Range), heartbeats persist, and **seek-to-end shows partial %** while
   full linear playback approaches 100%. Confirm `watch-status` reflects it.

---

## 10. File manifest

**Backend**
- `app/models/attendance.py` — add recording columns to `Meeting`; new `WatchProgress`.
- `alembic/versions/<rev>_recording_watch_tracking.py` — migration.
- `app/utils/recording_storage.py` — R2 boto3 helper (NEW).
- `app/workers/recording_tasks.py` — ingest task + seams (NEW).
- `app/api/webhooks.py` — `recording.completed` branch.
- `app/api/recordings.py` — session-scoped watch-tracking routes (NEW).
- `app/schemas/recording.py` — request/response models (NEW).
- `app/core/config.py` + `.env.example` — `R2_*`, `RECORDING_URL_TTL_SECS`.
- `app/main.py` — include the recordings router.
- `tests/test_recording_*.py` — heartbeat/ingest/api (NEW).

**Frontend**
- `src/pages/RecordingPlayerPage.tsx` (NEW) + route registration.
- `src/hooks/useRecording.ts` — url/progress/heartbeat/watch-status (NEW).
- (Dev A seam: `VideoCard` "Resume" → this route + `watch-status` progress — noted, not built here.)
