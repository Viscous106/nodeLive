# Branch B — Live Meeting & Meeting SDK Integration

**Branch:** `feat/live-meeting`  
**Owner:** Dev B  
**Base branch:** `main` (foundation skeleton already merged)  
**Estimated time:** 4 days  
**Stack:** React 19 + TSX (frontend) | Python 3.12 + FastAPI + python-socketio (backend)  
**This is the core differentiator — what makes nodeLive unique vs Scaler**

**Status:** ✅ **Implemented.** Milestones M1–M7 plus the live-Zoom follow-up (S2S
meeting create + host ZAK start) are built and tested — see the verified checklist
at the end. Still pending: M8 post-meeting AI pipeline, M9 recommendations/engagement
analytics, and full MP hardening (Sentry, k6, Prometheus, GH Actions).

---

## Scope

Build the live meeting experience: Zoom Meeting SDK embedded in a production-grade dashboard panel alongside 11 real-time features. This is the page students reach when they click "Join Session" on the session detail page.

**URL:** `/live/:sessionId`  
**Route:** Only accessible during LIVE sessions (status = LIVE) or if user is INSTRUCTOR

**The 11 features:**
1. Cue Cards (instructor → all students)
2. Quiz Engine (server-side timer, server-side scoring)
3. Polls (live result streaming)
4. AI Chat (Claude, streaming responses, within class context — + Groq fallback per plan.md §7.4a)
5. Live Bookmarks (timestamp markers)
6. Leaderboard (real-time, updates on quiz/poll)
7. Notice Board (instant push to all students)
8. Pinned Message (persistent banner at top of chat panel)
9. Raise Hand (queue for instructor)
10. Assignment Unlocking (LMS integration — instant notification)
11. Lecture Notes panel (upload during or after class)

---

## Architecture: The Split-Pane Live Meeting Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  TopBar: ← {title}    [LIVE ●]    Attendees: 24    [Leave]       │
├──────────────────────────────────────┬───────────────────────────┤
│                                      │  [Chat][Quiz][Poll][More] │
│                                      │  ┌─────────────────────┐  │
│   ZOOM COMPONENT VIEW                │  │                     │  │
│   (Zoom SDK renders here)            │  │  Feature Panel      │  │
│   width: 70%                         │  │  (tab-driven)       │  │
│                                      │  │                     │  │
│                                      │  │                     │  │
│                                      │  └─────────────────────┘  │
│                                      │                           │
│   [CueCardOverlay — slides in]       │  [PinnedMessageBanner]    │
│                                      │                           │
└──────────────────────────────────────┴───────────────────────────┘
```

**Panel tabs (right side):**
- Chat + AI (💬)
- Quiz (🎯)
- Poll (📊)
- Leaderboard (🏆)
- Bookmarks (🔖)
- Notes (📝)

**Instructor-only additional controls (inside tabs):**
- Cue Card advance button
- Poll create + close
- Quiz launch
- Notice push
- Message pin
- Assignment unlock
- Raise hand queue

---

## Day-by-Day Task Breakdown

### Day 1 — Backend Core + Zoom JWT

**Morning: Foundation routes**

1. `backend/app/api/live.py` — The live-meeting API module:
   ```python
   # JWT signature generation (ported from nodeLive testing/server.js)
   @router.post("/api/sessions/{session_id}/join")
   async def get_zoom_signature(
       session_id: str,
       body: JoinRequest,
       user: User = Depends(get_current_user),
       db: AsyncSession = Depends(get_db),
   ) -> JoinResponse:
       # 1. Verify enrollment
       # 2. Generate HS256 JWT for Zoom SDK (same logic as testing/server.js)
       # 3. Return { signature, sdkKey, zoomMeetingId }
   ```

2. `backend/app/utils/zoom_jwt.py` — Zoom SDK JWT generation in Python:
   ```python
   import hmac, hashlib, base64, json, time
   
   def generate_zoom_signature(sdk_key: str, sdk_secret: str, 
                               meeting_number: str, role: int) -> str:
       iat = int(time.time()) - 30
       exp = iat + 7200  # 2 hours
       
       header = base64.urlsafe_b64encode(
           json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
       ).rstrip(b'=').decode()
       
       payload = base64.urlsafe_b64encode(json.dumps({
           "appKey": sdk_key, "mn": meeting_number,
           "role": role, "iat": iat, "exp": exp, "tokenExp": exp,
       }).encode()).rstrip(b'=').decode()
       
       msg = f"{header}.{payload}"
       sig = base64.urlsafe_b64encode(
           hmac.new(sdk_secret.encode(), msg.encode(), hashlib.sha256).digest()
       ).rstrip(b'=').decode()
       
       return f"{msg}.{sig}"
   ```

3. `backend/app/api/live.py` — State snapshot endpoint:
   ```python
   @router.get("/api/sessions/{session_id}/live/state")
   async def get_live_state(session_id: str, ...) -> LiveStateOut:
       # Returns full current state for reconnecting clients
       # current_cue_card, active_poll, active_quiz, pinned_message,
       # recent_notices, user_bookmarks, my_quiz_score, leaderboard[:10]
   ```

4. `backend/app/models/live_meeting.py` — All live meeting models:
   ```python
   # CueCard, Poll, PollResponse, Quiz, QuizQuestion, QuizResponse
   # Bookmark, Notice, PinnedMessage, LeaderboardPoint
   # (full SQLAlchemy models from plan.md §4)
   ```

5. Alembic migration: `002_live_meeting_tables.py`

**Afternoon: WebSocket server**

6. `backend/app/realtime/server.py`:
   ```python
   import socketio, os
   from socketio import AsyncRedisManager
   
   sio = socketio.AsyncServer(
       async_mode="asgi",
       client_manager=AsyncRedisManager(os.environ["REDIS_URL"]),
       cors_allowed_origins=os.environ.get("CORS_ORIGIN", "*").split(","),
   )
   
   @sio.event
   async def connect(sid, environ, auth):
       # Validate JWT from cookie
       # Save session: { user_id, role, session_id }
       pass
   
   @sio.event
   async def join_session(sid, data):
       session_id = data["sessionId"]
       await sio.enter_room(sid, f"session:{session_id}")
       if user_role == "INSTRUCTOR":
           await sio.enter_room(sid, f"session:{session_id}:instructor")
       # Also join private room for AI responses
       await sio.enter_room(sid, f"session:{session_id}:{user_id}")
   
   @sio.event
   async def caption_received(sid, data):
       # Buffer captions in Redis sorted set for AI context
       session_id = data["sessionId"]
       await redis.zadd(f"captions:{session_id}", {data["text"]: data["timestamp"]})
       await redis.zremrangebyrank(f"captions:{session_id}", 0, -51)
   ```

7. `backend/app/main.py` — Mount socketio:
   ```python
   from socketio import ASGIApp
   from app.realtime.server import sio
   
   fastapi_app = FastAPI(...)
   socket_app = ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path="/socket.io")
   # Start uvicorn on socket_app, not fastapi_app
   ```

---

### Day 2 — Real-Time Feature APIs + Socket Events

**Cue Cards**

1. `POST /api/sessions/:id/live/cue-cards` — instructor creates card (content, displayOrder)
2. `PATCH /api/sessions/:id/live/cue-cards/:cardId/show` — marks card shown, emits `cuecard:shown`
3. `GET /api/sessions/:id/live/cue-cards` — list all cards

Socket event: `cuecard:shown → { cardId, content, order }`  
Room: `session:{id}` (all)

**Polls**

4. `POST /api/sessions/:id/live/polls` — create + emit `poll:launched`
5. `POST /api/sessions/:id/live/polls/:pollId/respond` — record response, recompute % + emit `poll:results`
6. `DELETE /api/sessions/:id/live/polls/:pollId/close` — close + emit `poll:closed`

Socket events: `poll:launched`, `poll:results`, `poll:closed`

**Quiz Engine**

7. `POST /api/sessions/:id/live/quiz` — create quiz (title, timeLimitSecs, questions[])
8. `POST /api/sessions/:id/live/quiz/:quizId/launch` — start quiz:
   ```python
   # Emit quiz:launched
   await sio.emit("quiz:launched", {...}, room=f"session:{session_id}")
   # Schedule first question timer via Celery
   from app.workers.quiz_tasks import advance_question
   advance_question.apply_async(
       args=[quiz_id, 0, session_id],
       countdown=quiz.time_limit_secs,
   )
   ```
9. `POST /api/sessions/:id/live/quiz/:quizId/respond` — score answer:
   - Correct: `base_points × (time_remaining / time_limit)`, clamp 2–10
   - Write to quiz_responses + leaderboard_points
   - Emit `quiz:score` to private room
   - Emit updated `leaderboard:update` to session room

10. `backend/app/workers/quiz_tasks.py` — Celery task:
    ```python
    @celery_app.task(name="quiz.advance_question")
    def advance_question(quiz_id: str, question_index: int, session_id: str):
        # Get quiz questions, advance to next or emit quiz:ended
        # Uses sync Redis connection (Celery is not async)
        ...
    ```

**Notices, Pinned Message, Raise Hand**

11. `POST /api/sessions/:id/live/notices` → DB write + emit `notice:pushed`
12. `PUT /api/sessions/:id/live/pinned-message` → upsert + emit `message:pinned`
13. Socket events for raise hand:
    - `raise_hand_up` event from client → emit `raise_hand:up` to instructor room
    - `raise_hand_down` from instructor → emit `raise_hand:down` to session room

**Bookmarks**

14. `POST /api/sessions/:id/live/bookmarks` — `{timestampMs, label}` → DB write, return bookmark
15. `GET /api/sessions/:id/live/bookmarks` — user's bookmarks for this session

**Assignment Unlocking**

16. `PATCH /api/sessions/:id/assignments/:assignmentId/unlock` → set `unlocked_at = now()` + emit `assignment:unlocked`

---

### Day 3 — Frontend Live Meeting Page

**Core Layout**

1. `frontend/src/pages/LiveMeetingPage.tsx`:
   ```tsx
   // On mount: fetch session state, connect socket, init Zoom SDK
   // On leave: disconnect socket, call leaveMeeting()
   export default function LiveMeetingPage() {
     const { sessionId } = useParams()
     const { data: session } = useSession(sessionId)
     const { data: liveState } = useLiveState(sessionId)
     
     return (
       <div className="h-screen flex flex-col bg-black overflow-hidden">
         <LiveMeetingTopBar session={session} />
         <div className="flex flex-1 overflow-hidden">
           <ZoomPanel sessionId={sessionId} className="flex-[7]" />
           <FeaturePanel sessionId={sessionId} className="w-[360px]" liveState={liveState} />
         </div>
         <CueCardOverlay />
         <NoticeOverlay />
       </div>
     )
   }
   ```

2. `frontend/src/components/live-meeting/LiveMeetingTopBar.tsx`:
   ```
   height: 48px, bg: #1A1A2E (dark), text: white
   Left: ← {session.title}
   Center: [LIVE ●] red dot + "LIVE" text (red), "Attendees: {count}"
   Right: [Leave Meeting] red outlined button
   ```

3. `frontend/src/components/live-meeting/ZoomPanel.tsx`:
   ```tsx
   // Ported + improved from testing/src/App.tsx
   // Key improvements per plan.md Appendix D:
   //   - patchJsMedia: true
   //   - leaveOnPageUnload: true
   //   - sdkKey passed to client.join()
   //   - zak: '' (empty for students)
   
   export function ZoomPanel({ sessionId }: Props) {
     const zoomRootRef = useRef<HTMLDivElement>(null)
     const { joinMeeting, leaveMeeting, status } = useZoomSDK(zoomRootRef, sessionId)
     
     return (
       <div className="relative h-full bg-black">
         <div ref={zoomRootRef} className="w-full h-full" id="zoomAppRoot" />
         {status === 'idle' && <ZoomLoadingState onJoin={joinMeeting} />}
       </div>
     )
   }
   ```

4. `frontend/src/hooks/useZoomSDK.ts`:
   ```ts
   // Centralizes ALL Zoom SDK logic:
   // - createClient() once in useRef
   // - fetch /api/sessions/:id/join → { signature, sdkKey, zoomMeetingId }
   // - client.init() with all required options
   // - client.join() with customerKey = user.id.slice(0, 35)
   // - Attach: user-added, user-removed events → attendee count
   // - Caption events: client.on('caption-message') → emit caption:received to socket
   // - Cleanup: destroyClient() on unmount
   ```

5. `frontend/src/components/live-meeting/FeaturePanel.tsx`:
   ```tsx
   // Right panel with tab navigation
   const TABS = [
     { id: 'chat', icon: MessageSquare, label: 'Chat' },
     { id: 'quiz', icon: Target, label: 'Quiz' },
     { id: 'poll', icon: BarChart3, label: 'Poll' },
     { id: 'leaderboard', icon: Trophy, label: 'Board' },
     { id: 'bookmarks', icon: Bookmark, label: 'Marks' },
     { id: 'notes', icon: FileText, label: 'Notes' },
   ]
   // Tab icons on right edge (48px wide), content area fills rest
   // Same design as Scaler's video lecture right panel (dark navy bg)
   // bg: #1A1A2E (dark navy) for instructor-mode, white for student-mode
   // Actually: use bg-[#1A1A2E] for the panel during live meeting
   ```

**Feature Panel Tabs (all as sub-components)**

6. `frontend/src/components/live-meeting/panels/ChatPanel.tsx`:
   ```
   Chat messages list (scrollable)
   Pinned message: yellow banner at top if pinnedMessage exists
   Message input: text field + [Send] button
   [/ai prefix] → triggers AI chat → shows streaming response in chat
   AI response: blue-bordered message bubble with "AI" label
   ```

7. `frontend/src/components/live-meeting/panels/QuizPanel.tsx`:
   ```
   Student view:
     When quiz active: question + 4 options (A/B/C/D radio) + countdown timer
     After answer: show correct/wrong + score earned
     Between questions: waiting state
   Instructor view:
     Quiz creator: title + add questions (question text, 4 options, correct answer)
     [Launch Quiz] button
     Live progress: % of students answered
   ```

8. `frontend/src/components/live-meeting/panels/PollPanel.tsx`:
   ```
   Student view:
     Active poll: question + option buttons → click to vote
     After vote: live bar chart showing % per option (updates via socket)
   Instructor view:
     Poll creator: question + 4 options + [Launch Poll] button
     [Close Poll] button when active
     Live results bar chart
   ```

9. `frontend/src/components/live-meeting/panels/LeaderboardPanel.tsx`:
   ```
   Top 10 list:
   #1 🥇 [Avatar] Display Name .......... 87 pts
   #2 🥈 [Avatar] Display Name .......... 75 pts
   ...
   Highlight: current user's row (light blue bg)
   Updates live via leaderboard:update socket event
   ```

10. `frontend/src/components/live-meeting/panels/BookmarkPanel.tsx`:
    ```
    List of user's bookmarks:
    [🔖] "Interesting point about X"  14:32
    [🔖] (unlabeled)                  23:41
    [+ Add Bookmark] button → POST /bookmarks with current class time
    Label input: optional text field
    Post-class: timestamps become clickable (scrub recording)
    ```

11. `frontend/src/components/live-meeting/panels/NotesPanel.tsx`:
    ```
    List of lecture notes uploaded by instructor:
    [📄] Isolation Levels - Lecture Notes.pdf  [↓ Download]
    [AI Generated] Meeting Summary (generated after class)
    Instructor-only: [Upload Notes] file picker (PDF/DOCX)
    ```

**Overlays**

12. `frontend/src/components/live-meeting/overlays/CueCardOverlay.tsx`:
    ```
    Position: absolute right-[380px] bottom-16 (on top of Zoom panel, right side)
    Width: 320px, max-height: 200px
    bg: white, border-radius: 12px, shadow-elevated
    Slide-in animation: translateX(120%) → 0, 300ms ease-out
    Auto-dismiss: after 30 seconds
    Content: card text (body, 16px) + "Card {n} of {total}" label
    Instructor only: [Show Next] button + keyboard shortcut →
    ```

13. `frontend/src/components/live-meeting/overlays/NoticeOverlay.tsx`:
    ```
    CRITICAL notice → full-screen modal (darkened backdrop, card center)
    NORMAL notice → slide-in banner from top (below TopBar)
    Dismiss button: × icon
    ```

14. `frontend/src/components/live-meeting/instructor/RaiseHandQueue.tsx`:
    ```
    Instructor panel section (in Chat tab):
    "✋ Raised Hands" header
    Queue list: [Avatar] Name [Call On] button
    Click "Call On" → emits raise_hand_down, could spotlight user
    ```

---

### Day 4 — AI Chat + Polish + Testing

**AI Chat (streaming)**

1. `backend/app/api/ai_chat.py`:
   ```python
   @router.post("/api/sessions/{session_id}/live/ai-chat")
   async def ai_chat(session_id: str, body: AiChatRequest, user: User = ...):
       # Get last 50 captions from Redis
       captions_raw = await redis.zrange(f"captions:{session_id}", 0, -1)
       captions = [c.decode() for c in captions_raw]
       
       # Stream Claude response
       client = anthropic.AsyncAnthropic()
       async with client.messages.stream(
           model="claude-sonnet-4-6",
           max_tokens=1024,
           system=f"""You are an AI teaching assistant for a live meeting titled "{session.title}".
   Current lecture context (last 50 transcription segments):
   {' '.join(captions)}
   Answer the student's question concisely. Do not make up facts.""",
           messages=[{"role": "user", "content": body.message}],
       ) as stream:
           async for chunk in stream.text_stream:
               # Emit to user's private socket room
               await sio.emit(
                   "ai:response-chunk",
                   {"chunk": chunk},
                   room=f"session:{session_id}:{user.id}",
               )
           await sio.emit(
                   "ai:response-done",
                   {},
                   room=f"session:{session_id}:{user.id}",
               )
       return {"status": "ok"}
   ```

2. `frontend/src/hooks/useAiStream.ts`:
   ```ts
   export function useAiStream(sessionId: string) {
     const [chunks, setChunks] = useState<string[]>([])
     const [isStreaming, setIsStreaming] = useState(false)
     const socket = useSocket()
     
     useEffect(() => {
       socket.on('ai:response-chunk', ({ chunk }) => {
         setChunks(prev => [...prev, chunk])
       })
       socket.on('ai:response-done', () => setIsStreaming(false))
       return () => { socket.off('ai:response-chunk'); socket.off('ai:response-done') }
     }, [socket])
     
     const sendMessage = async (message: string) => {
       setChunks([])
       setIsStreaming(true)
       await api.post(`/sessions/${sessionId}/live/ai-chat`, { message })
     }
     
     return { response: chunks.join(''), isStreaming, sendMessage }
   }
   ```

**Real-time state hooks**

3. `frontend/src/hooks/useSocket.ts` — Socket.io connection singleton with auto-reconnect
4. `frontend/src/hooks/useLiveState.ts` — hydrates store from `/live/state` on join + reconnect
5. `frontend/src/stores/liveClassStore.ts` — Zustand store for all live state:
   ```ts
   interface LiveMeetingStore {
     currentCueCard: CueCard | null
     activePoll: Poll | null
     activeQuiz: Quiz | null
     activeQuestion: QuizQuestion | null
     timeLeft: number
     pinnedMessage: string | null
     notices: Notice[]
     raisedHands: RaisedHand[]
     leaderboard: RankedUser[]
     myScore: number
     bookmarks: Bookmark[]
     attendeeCount: number
     // Setters called by socket event handlers
     setCueCard, setPoll, setQuiz, addNotice, setLeaderboard, ...
   }
   ```

**Socket event binding** (`frontend/src/hooks/useSocketEvents.ts`):
```ts
// Binds all incoming socket events to liveClassStore updates
socket.on('cuecard:shown', store.setCueCard)
socket.on('poll:launched', store.setPoll)
socket.on('poll:results', store.updatePollResults)
socket.on('poll:closed', () => store.setPoll(null))
socket.on('quiz:launched', store.setQuiz)
socket.on('quiz:next-question', store.setQuestion)
socket.on('quiz:ended', () => store.setQuiz(null))
socket.on('quiz:score', store.setMyScore)
socket.on('leaderboard:update', store.setLeaderboard)
socket.on('notice:pushed', store.addNotice)
socket.on('message:pinned', store.setPinnedMessage)
socket.on('assignment:unlocked', (a) => toast.success(`"${a.title}" is now unlocked!`))
socket.on('raise_hand:up', store.addRaisedHand)
socket.on('raise_hand:down', store.removeRaisedHand)
```

**Polish**

5. Quiz countdown timer: `useEffect` + `setInterval` to tick `timeLeft` down each second
6. Toast notifications for: assignment unlock, new notice (NORMAL priority), quiz score reveal
7. Instructor-only UI gating: check `user.role === 'INSTRUCTOR'` before rendering controls
8. Error handling: Zoom SDK join failures show red banner with message
9. Leave confirmation dialog: "Are you sure you want to leave the class?"

---

## Backend File Structure (Branch B owns)

```
backend/
├── app/
│   ├── api/
│   │   ├── live.py          ← NEW (join, state, cue-cards, polls, quiz, etc.)
│   │   ├── ai_chat.py       ← NEW (streaming Claude response)
│   │   ├── bookmarks.py     ← NEW
│   │   ├── assignments.py   ← NEW (unlock endpoint)
│   │   └── webhooks.py      ← NEW (Zoom webhooks — ported from testing/)
│   ├── models/
│   │   ├── live_meeting.py    ← NEW
│   │   ├── lms.py           ← NEW (Assignment, LectureNote)
│   │   └── attendance.py    ← NEW (ported from testing/lib/db.js)
│   ├── schemas/
│   │   ├── live.py          ← NEW (LiveStateOut, CueCardOut, PollOut, etc.)
│   │   └── ai.py            ← NEW (AiChatRequest)
│   ├── realtime/
│   │   └── server.py        ← NEW (python-socketio ASGI)
│   ├── workers/
│   │   ├── celery_app.py    ← SHARED (from foundation)
│   │   ├── quiz_tasks.py    ← NEW (advance_question)
│   │   └── ai_tasks.py      ← NEW (post-meeting summary — sprint 2)
│   └── utils/
│       ├── zoom_jwt.py      ← NEW (signature generation)
│       └── intervals.py     ← NEW (ported from testing/lib/intervals.js)
└── alembic/versions/
    └── 002_live_meeting_tables.py ← NEW
```

---

## Frontend File Structure (Branch B owns)

```
frontend/src/
├── pages/
│   └── LiveMeetingPage.tsx           ← NEW
├── components/
│   └── live-meeting/
│       ├── LiveMeetingTopBar.tsx     ← NEW
│       ├── ZoomPanel.tsx           ← NEW
│       ├── FeaturePanel.tsx        ← NEW
│       ├── panels/
│       │   ├── ChatPanel.tsx       ← NEW
│       │   ├── QuizPanel.tsx       ← NEW
│       │   ├── PollPanel.tsx       ← NEW
│       │   ├── LeaderboardPanel.tsx ← NEW
│       │   ├── BookmarkPanel.tsx   ← NEW
│       │   └── NotesPanel.tsx      ← NEW
│       ├── overlays/
│       │   ├── CueCardOverlay.tsx  ← NEW
│       │   └── NoticeOverlay.tsx   ← NEW
│       └── instructor/
│           ├── InstructorControls.tsx ← NEW
│           └── RaiseHandQueue.tsx     ← NEW
├── hooks/
│   ├── useZoomSDK.ts               ← NEW
│   ├── useSocket.ts                ← NEW
│   ├── useLiveState.ts             ← NEW
│   ├── useAiStream.ts              ← NEW
│   └── useSocketEvents.ts          ← NEW
└── stores/
    └── liveClassStore.ts           ← NEW
```

---

## Zoom SDK Notes (Critical — from nodeLive testing/ + Appendix D)

```ts
// Must-have in client.init():
await client.init({
  zoomAppRoot: zoomRootRef.current,
  language: 'en-US',
  patchJsMedia: true,       // Safari/Firefox compat
  leaveOnPageUnload: true,  // Prevents zombie sessions
  debug: true,
  customize: {
    video: { isResizable: true, viewSizes: { default: { width: 1000, height: 600 } } },
    meetingInfo: ['topic', 'host', 'mn', 'pwd', 'invite', 'participant'],
  },
})

// Must-have in client.join():
await client.join({
  signature,               // from /api/sessions/:id/join
  sdkKey,                  // from same response (must not be discarded)
  meetingNumber,
  password,
  userName: user.displayName,
  userEmail: user.email,
  customerKey: user.id.slice(0, 35),  // identity bridge for webhooks
  zak: '',                 // empty for students, host token for instructors
})
```

**COOP/COEP headers** (already in `testing/vite.config.ts` — port to production nginx and keep in Vite):
```ts
// vite.config.ts
server: {
  headers: {
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Embedder-Policy': 'require-corp',
  }
}
```

**SDK version:** Keep `@zoom/meetingsdk@^6.1.0` — already tested in nodeLive  
**Import pattern:**
```ts
import * as ZoomSDK from '@zoom/meetingsdk/embedded'
const ZoomMtgEmbedded = ((ZoomSDK as any).default ?? ZoomSDK) as typeof import('@zoom/meetingsdk/embedded').default
```

**Webhook porting** (from `testing/routes/webhooks.js`):
- Port HMAC-SHA256 raw body verification to FastAPI (use `Request` object to get raw bytes)
- Keep all event handlers: `meeting.started`, `meeting.ended`, `meeting.participant_joined`, `meeting.participant_left`

---

## Socket Event Catalog (complete reference)

### Instructor → Server → All Students
| Event | Payload | Emitted on |
|-------|---------|-----------|
| `cuecard:shown` | `{ cardId, content, order }` | PATCH /cue-cards/:id/show |
| `poll:launched` | `{ pollId, question, options, closesAt }` | POST /polls |
| `poll:results` | `{ pollId, results: [{optionId, count, pct}] }` | Any response |
| `poll:closed` | `{ pollId, finalResults }` | DELETE /polls/:id/close |
| `quiz:launched` | `{ quizId, title, timeLimitSecs }` | POST /quiz/:id/launch |
| `quiz:next-question` | `{ questionId, question, options, timeLeft }` | Celery task |
| `quiz:ended` | `{ quizId, topScores }` | Celery task (final question) |
| `notice:pushed` | `{ noticeId, content, priority, expiresAt }` | POST /notices |
| `notice:dismissed` | `{ noticeId }` | DELETE /notices/:id |
| `message:pinned` | `{ message, pinnedBy }` | PUT /pinned-message |
| `message:unpinned` | `{}` | DELETE /pinned-message |
| `assignment:unlocked` | `{ assignmentId, title, dueAt }` | PATCH /assignments/:id/unlock |

### Student → Server → Others
| Event | Payload | Direction |
|-------|---------|----------|
| `raise_hand_up` | `{ userId, name }` | Client → Server → instructor room |
| `raise_hand_down` | `{ userId }` | Client → Server → session room |
| `caption_received` | `{ sessionId, text, timestamp }` | Client → Server (Redis buffer) |

### Server → Single User (private room)
| Event | Payload | Trigger |
|-------|---------|---------|
| `quiz:score` | `{ score, correct, explanation }` | Quiz answer graded |
| `ai:response-chunk` | `{ chunk }` | Claude streaming |
| `ai:response-done` | `{}` | Stream complete |

### Shared (after any quiz answer)
| Event | Payload | Room |
|-------|---------|------|
| `leaderboard:update` | `{ rankings: [{userId, name, points, rank}] }` | session |

---

## Checklist

### Backend
- [x] Zoom JWT signature generator (zoom_jwt.py) — test with actual SDK key
- [x] `POST /api/sessions/:id/join` — returns signature + sdkKey (+ zoomMeetingId, password, zak)
- [x] `GET /api/sessions/:id/live/state` — full state snapshot
- [x] Live class SQLAlchemy models (CueCard, Poll, Quiz, Bookmark, Notice, PinnedMessage, LeaderboardPoint)
- [x] Alembic migration (`3a0dd075c00f_live_meeting_tables.py`)
- [x] python-socketio ASGI server mounted in main.py
- [x] Socket connect handler with JWT validation
- [x] join_session event → room join
- [x] caption_received event → Redis buffer
- [x] Cue card CRUD routes + cuecard:shown emit
- [x] Poll create/respond/close routes + socket events
- [x] Quiz create + launch route + Celery timer task
- [x] Quiz respond route with scoring algorithm
- [x] Notice create route + notice:pushed emit
- [x] Pinned message PUT/DELETE + socket events
- [x] Raise hand socket events (no DB — ephemeral)
- [x] Bookmark create + list routes
- [x] Assignment unlock route + assignment:unlocked emit
- [x] Leaderboard update on quiz/poll response
- [x] AI chat route (streaming Claude + socket chunks) — Groq fallback per plan.md §7.4a
- [x] Zoom webhook handler (ported from testing/routes/webhooks.js)
- [x] intervals.py port from intervals.js (with pytest tests)
- [x] pytest tests for: zoom_jwt, quiz scoring, poll results calculation
- [x] **M7 recordings:** `app/api/recordings.py`, `app/utils/recording_storage.py`, `app/workers/recording_tasks.py`, `app/utils/watch.py`, `app/schemas/recording.py`, migration `rec0watch7m7a_*` + `recording.completed` webhook branch
- [x] **M+ live Zoom:** `app/utils/zoom_meetings.py` (S2S create-meeting + host ZAK); host-start flips session LIVE

### Frontend
- [x] LiveMeetingPage.tsx with split-pane layout
- [x] LiveMeetingTopBar (dark, LIVE indicator, attendee count, leave button)
- [x] ZoomPanel.tsx — SDK init in useRef, join on mount
- [x] useZoomSDK.ts hook (all SDK logic, caption event forwarding)
- [x] FeaturePanel.tsx with tab bar (icon tabs on right edge)
- [x] ChatPanel with pinned message banner + AI integration
- [x] QuizPanel (student countdown + instructor creator)
- [x] PollPanel (student vote + live bar chart + instructor creator)
- [x] LeaderboardPanel (top 10, highlight current user)
- [x] BookmarkPanel (list + add button)
- [x] NotesPanel (list + instructor upload)
- [x] CueCardOverlay (slide-in, 30s auto-dismiss)
- [x] NoticeOverlay (full-screen CRITICAL + banner NORMAL)
- [x] RaiseHandQueue (instructor panel inside ChatPanel)
- [x] useSocket.ts (singleton, reconnect)
- [x] useSocketEvents.ts (all event → store bindings)
- [x] useLiveState.ts (hydrate on join/reconnect)
- [x] liveClassStore.ts (Zustand)
- [x] useAiStream.ts (socket-driven streaming display)
- [x] COOP/COEP headers in vite.config.ts
- [x] Leave meeting dialog confirmation
- [x] Toast notifications (assignment unlock, quiz score, new notice)
- [x] **M7:** RecordingPlayerPage.tsx + useRecording.ts (watch-tracking player)
