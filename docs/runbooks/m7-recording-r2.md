# Runbook — M7 Recording Storage (Cloudflare R2) Setup + T13 Verification

This is the turnkey procedure to take recording ingest + watch-tracking from
"seam-tested" to **live against real Cloudflare R2**, and to run the final
end-to-end (T13) check. Everything upstream of the physical R2 round-trip is
already verified in CI + local smoke runs; this runbook covers the cloud half.

> **Why R2:** S3-compatible, generous free tier, no egress fees. The backend
> talks to it via boto3 (`app/utils/recording_storage.py`) using the standard S3
> API, so the exact same code also works against AWS S3 or a local MinIO.

---

## 1. Provision the bucket + token (Cloudflare dashboard)

1. **R2 → Create bucket** → name it e.g. `linkhq-recordings`. Note your **Account ID**.
2. **R2 → Manage R2 API Tokens → Create API Token**:
   - Permissions: **Object Read & Write**.
   - Scope: the `linkhq-recordings` bucket.
   - Save the **Access Key ID** and **Secret Access Key** (shown once).
3. Your S3 endpoint is `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.

## 2. Backend `.env`

Set in `backend/.env` (all blank by default → the app returns **501** and
ingest no-ops, so partial config degrades gracefully):

```bash
R2_ACCOUNT_ID=<account_id>
R2_ACCESS_KEY_ID=<access_key_id>
R2_SECRET_ACCESS_KEY=<secret_access_key>
R2_BUCKET=linkhq-recordings
R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
RECORDING_URL_TTL_SECS=300
```

## 3. Bucket CORS — **the deploy trap**

The live Zoom SDK forces `Cross-Origin-Embedder-Policy: require-corp` app-wide.
A `<video crossorigin="anonymous">` pulling a presigned R2 URL is a cross-origin
subresource: it loads only if the bucket CORS allows the app origin, **allows the
`Range` request header, and exposes `Content-Range` / `Accept-Ranges` /
`Content-Length`**. If `Range` isn't allowed/exposed, the video may load but
**seeking silently breaks** — and seeking is the whole point of watch-tracking.

In **R2 → bucket → Settings → CORS Policy**, set (replace origins with your real
dev + prod origins):

```json
[
  {
    "AllowedOrigins": [
      "http://localhost:5173",
      "https://app.your-domain.com"
    ],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["Range", "Content-Type"],
    "ExposeHeaders": ["Content-Range", "Accept-Ranges", "Content-Length", "ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

## 4. Zoom auto-ingest (optional — needs paid Zoom cloud recording)

To have recordings flow in automatically, also set the S2S OAuth + webhook env
(`ZOOM_S2S_ACCOUNT_ID/CLIENT_ID/CLIENT_SECRET`, `ZOOM_WEBHOOK_SECRET_TOKEN`) and
subscribe the Zoom app to **`recording.completed`** pointing at
`POST /api/webhooks/zoom`. The handler marks the meeting `pending` and enqueues
`recording.ingest` (Celery), which downloads the MP4 and streams it to R2. This
path is ported verbatim and seam-tested but only runs with a paid Zoom plan.

For T13 you do **not** need this — seed a recording manually (step 6).

---

## 5. Automated verification (no browser) — the storage round-trip

The opt-in integration test exercises the real boto3 upload + presign + **Range**
against your bucket (or a local MinIO). Skipped by default; run on demand:

```bash
# Against real R2:
cd backend && source .venv/bin/activate
RUN_STORAGE_IT=1 \
R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com \
R2_ACCESS_KEY_ID=<id> R2_SECRET_ACCESS_KEY=<secret> R2_BUCKET=linkhq-recordings \
pytest tests/test_recording_storage_integration.py -v
```

Or against a throwaway local MinIO (identical S3 API — proves the path with zero
cloud cost):

```bash
docker run -d --name it-minio -p 9100:9000 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data
RUN_STORAGE_IT=1 \
R2_ENDPOINT_URL=http://localhost:9100 R2_ACCESS_KEY_ID=minioadmin \
R2_SECRET_ACCESS_KEY=minioadmin R2_BUCKET=linkhq-recordings \
pytest tests/test_recording_storage_integration.py -v
docker rm -f it-minio
```

Both assert: 1 MiB streamed up, full GET byte-exact, **Range → 206 with correct
`Content-Range`** (start + mid-file), `accept-ranges: bytes`, and `run_ingest`
landing the object under `recordings/<uuid>.mp4`.

---

## 6. T13 — full end-to-end (browser click-through)

1. Upload a real MP4 to the bucket as `recordings/e2e-1.mp4` (R2 dashboard or
   `aws s3 cp --endpoint-url ...`).
2. Point a past session's Meeting at it (host/admin login, or enroll your user
   in the session's course):

   ```bash
   cd backend && source .venv/bin/activate && python - <<'PY'
   import asyncio
   from datetime import UTC, datetime
   from sqlalchemy import select
   from app.db.session import AsyncSessionLocal
   from app.models.attendance import Meeting
   from app.models.course import ClassSession

   SESSION_ID = "seed-session-past-1"   # any ENDED session you can access
   async def go():
       async with AsyncSessionLocal() as db:
           cs = await db.get(ClassSession, SESSION_ID)
           m = await db.scalar(select(Meeting).where(Meeting.zoom_uuid == "e2e-1"))
           if m is None:
               m = Meeting(zoom_uuid="e2e-1"); db.add(m)
           m.zoom_meeting_id = cs.zoom_meeting_id
           m.recording_s3_key = "recordings/e2e-1.mp4"
           m.recording_status = "stored"
           m.recording_duration_secs = <REAL_MP4_DURATION_SECS>
           m.ended_at = datetime(2026, 1, 1, tzinfo=UTC)
           await db.commit()
           print("pointed", SESSION_ID, "→ recordings/e2e-1.mp4")
   asyncio.run(go())
   PY
   ```

3. Run backend (`uvicorn app.main:socket_app --reload --port 8000`) + frontend
   (`npm run dev`), open `/session/seed-session-past-1/recording`. Confirm:
   1. Video loads from the presigned R2 URL.
   2. **Seeking works** (drag the scrubber → Range requests succeed).
   3. Play 0→N, reload → resumes near N, % climbs.
   4. Reload fresh, **seek to the end and play the last few seconds** → % stays
      low (partial), **not ~100%**. This is the compliance proof.
   5. `GET /api/sessions/seed-session-past-1/recording/watch-status` reflects it.

4. Clean up the `e2e-1` Meeting row + the test object when done.

---

## Already-verified (you don't need to re-do these)

- Pure compliance core (`apply_heartbeat`, seek-to-end ≠ 100%) — unit tests.
- All 4 API routes, 404/501 gates, server-authoritative duration, membership
  gating — `tests/test_recording_api.py` (DB-backed).
- `recording.completed` webhook → pending + enqueue — `tests/test_webhooks.py`.
- Ingest wiring (token preference, mp4 pick, mark transitions) — seam tests.
- **Live storage round-trip + Range + presigned playback through the running
  app** — verified against MinIO (see `tests/test_recording_storage_integration.py`).

Only the literal Zoom-CDN download and the in-browser MP4 codec render require
the real cloud accounts; this runbook closes both.
