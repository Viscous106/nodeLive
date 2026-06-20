/**
 * Live-meeting client state (Zustand).
 *
 * Hydrated once from `GET /live/state` on join/reconnect, then mutated by
 * incoming socket events (see `useSocketEvents`). Components read slices of
 * this; they never talk to the socket directly for reads.
 */

import { create } from 'zustand'

import type {
  ActiveQuestion,
  Bookmark,
  CueCard,
  LiveState,
  Notice,
  PollOptionResult,
  Poll,
  Quiz,
  RaisedHand,
  RankedUser,
} from '@/types'

interface LiveClassState {
  currentCueCard: CueCard | null
  activePoll: Poll | null
  pollResults: PollOptionResult[]
  activeQuiz: Quiz | null
  activeQuestion: ActiveQuestion | null
  timeLeft: number
  lastScore: { points: number; correct: boolean } | null
  pinnedMessage: string | null
  notices: Notice[]
  bookmarks: Bookmark[]
  raisedHands: RaisedHand[]
  leaderboard: RankedUser[]
  myScore: number
  attendeeCount: number

  hydrate: (state: LiveState) => void
  reset: () => void

  setCueCard: (card: CueCard | null) => void
  setPoll: (poll: Poll | null) => void
  setPollResults: (results: PollOptionResult[]) => void
  setQuiz: (quiz: Quiz | null) => void
  setActiveQuestion: (q: ActiveQuestion | null) => void
  tick: () => void
  setScore: (score: { points: number; correct: boolean }) => void
  addPoints: (points: number) => void
  setPinnedMessage: (message: string | null) => void
  addNotice: (notice: Notice) => void
  removeNotice: (id: string) => void
  addBookmark: (bookmark: Bookmark) => void
  addRaisedHand: (hand: RaisedHand) => void
  removeRaisedHand: (userId: string) => void
  setLeaderboard: (ranking: RankedUser[]) => void
  setAttendeeCount: (count: number) => void
}

const initial = {
  currentCueCard: null,
  activePoll: null,
  pollResults: [],
  activeQuiz: null,
  activeQuestion: null,
  timeLeft: 0,
  lastScore: null,
  pinnedMessage: null,
  notices: [],
  bookmarks: [],
  raisedHands: [],
  leaderboard: [],
  myScore: 0,
  attendeeCount: 0,
}

export const useLiveClassStore = create<LiveClassState>((set) => ({
  ...initial,

  hydrate: (state) =>
    set({
      currentCueCard: state.currentCueCard,
      activePoll: state.activePoll,
      activeQuiz: state.activeQuiz,
      pinnedMessage: state.pinnedMessage,
      notices: state.recentNotices,
      bookmarks: state.userBookmarks,
      myScore: state.myQuizScore,
      leaderboard: state.leaderboard,
    }),
  reset: () => set(initial),

  setCueCard: (currentCueCard) => set({ currentCueCard }),
  setPoll: (activePoll) => set({ activePoll, pollResults: [] }),
  setPollResults: (pollResults) => set({ pollResults }),
  setQuiz: (activeQuiz) =>
    set(activeQuiz ? { activeQuiz } : { activeQuiz: null, activeQuestion: null }),
  setActiveQuestion: (activeQuestion) =>
    set({ activeQuestion, timeLeft: activeQuestion?.timeLeft ?? 0, lastScore: null }),
  tick: () => set((s) => ({ timeLeft: Math.max(0, s.timeLeft - 1) })),
  setScore: (lastScore) => set({ lastScore }),
  addPoints: (points) => set((s) => ({ myScore: s.myScore + points })),
  setPinnedMessage: (pinnedMessage) => set({ pinnedMessage }),
  addNotice: (notice) => set((s) => ({ notices: [notice, ...s.notices] })),
  removeNotice: (id) =>
    set((s) => ({ notices: s.notices.filter((n) => n.id !== id) })),
  addBookmark: (bookmark) =>
    set((s) => ({ bookmarks: [...s.bookmarks, bookmark] })),
  addRaisedHand: (hand) =>
    set((s) =>
      s.raisedHands.some((h) => h.userId === hand.userId)
        ? s
        : { raisedHands: [...s.raisedHands, hand] },
    ),
  removeRaisedHand: (userId) =>
    set((s) => ({ raisedHands: s.raisedHands.filter((h) => h.userId !== userId) })),
  setLeaderboard: (leaderboard) => set({ leaderboard }),
  setAttendeeCount: (attendeeCount) => set({ attendeeCount }),
}))
