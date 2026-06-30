/**
 * Binds every inbound live-meeting socket event to the live store (and a few
 * toasts). One effect, registered once per session; handlers read fresh setters
 * via `getState()` so there are no stale closures and no rebind churn.
 *
 * Event names + payloads mirror backend/app/api/live.py and the M3 catalog in
 * docs/branch-B-live-meeting.md.
 */

import { useEffect } from 'react'

import { getSocket } from '@/lib/socket'
import { useLiveClassStore } from '@/stores/liveClassStore'
import { toast } from '@/stores/toastStore'
import type { PollOptionResult, RankedUser } from '@/types'

export function useSocketEvents(sessionId: string): void {
  useEffect(() => {
    if (!sessionId) return
    const socket = getSocket()
    const store = useLiveClassStore.getState

    const onCueCard = (d: { cardId: string; content: string; order: number }) =>
      store().setCueCard({
        id: d.cardId,
        content: d.content,
        displayOrder: d.order,
        shownAt: new Date().toISOString(),
      })

    const onPollLaunched = (d: {
      pollId: string
      question: string
      options: string[]
    }) =>
      store().setPoll({
        id: d.pollId,
        question: d.question,
        options: d.options,
        status: 'OPEN',
      })

    const onPollResults = (d: { results: PollOptionResult[] }) =>
      store().setPollResults(d.results)

    const onPollClosed = (d: { results: PollOptionResult[] }) => {
      const cur = store().activePoll
      if (cur) store().setPoll({ ...cur, status: 'CLOSED' })
      store().setPollResults(d.results)
    }

    const onQuizLaunched = (d: {
      quizId: string
      title: string
      timeLimitSecs: number
    }) =>
      store().setQuiz({
        id: d.quizId,
        title: d.title,
        timeLimitSecs: d.timeLimitSecs,
        status: 'LIVE',
      })

    const onNextQuestion = (d: {
      quizId: string
      questionId: string
      index: number
      text: string
      options: string[]
      timeLeft: number
    }) => store().setActiveQuestion(d)

    const onQuizEnded = () => {
      store().setQuiz(null)
      toast({ variant: 'default', title: 'Quiz ended' })
    }

    const onQuizScore = (d: {
      questionId: string
      correct: boolean
      points: number
    }) => {
      store().setScore({ points: d.points, correct: d.correct })
      store().addPoints(d.points)
      toast({
        variant: d.correct ? 'success' : 'error',
        title: d.correct ? `+${d.points} points!` : 'Incorrect',
      })
    }

    const onLeaderboard = (d: { rankings: RankedUser[] }) =>
      store().setLeaderboard(d.rankings)

    const onNotice = (d: {
      noticeId: string
      content: string
      priority: string
    }) => {
      store().addNotice({
        id: d.noticeId,
        content: d.content,
        priority: d.priority,
        createdAt: new Date().toISOString(),
        expiresAt: null,
      })
      if (d.priority !== 'CRITICAL') {
        toast({ variant: 'default', title: 'Notice', description: d.content })
      }
    }

    const onNoticeDismissed = (d: { noticeId: string }) =>
      store().removeNotice(d.noticeId)

    const onPinned = (d: { message: string }) =>
      store().setPinnedMessage(d.message)
    const onUnpinned = () => store().setPinnedMessage(null)

    const onAssignmentUnlocked = (d: { title: string }) =>
      toast({ variant: 'success', title: `"${d.title}" is now unlocked!` })

    const onHandUp = (d: { userId: string; name?: string }) =>
      store().addRaisedHand({ userId: d.userId, name: d.name })
    const onHandDown = (d: { userId: string }) =>
      store().removeRaisedHand(d.userId)

    const onSessionEnded = () => {
      store().setSessionEnded(true)
      toast({ variant: 'default', title: 'The class has ended' })
    }

    socket.on('cuecard:shown', onCueCard)
    socket.on('poll:launched', onPollLaunched)
    socket.on('poll:results', onPollResults)
    socket.on('poll:closed', onPollClosed)
    socket.on('quiz:launched', onQuizLaunched)
    socket.on('quiz:next-question', onNextQuestion)
    socket.on('quiz:ended', onQuizEnded)
    socket.on('quiz:score', onQuizScore)
    socket.on('leaderboard:update', onLeaderboard)
    socket.on('notice:pushed', onNotice)
    socket.on('notice:dismissed', onNoticeDismissed)
    socket.on('message:pinned', onPinned)
    socket.on('message:unpinned', onUnpinned)
    socket.on('assignment:unlocked', onAssignmentUnlocked)
    socket.on('raise_hand:up', onHandUp)
    socket.on('raise_hand:down', onHandDown)
    socket.on('session:ended', onSessionEnded)

    return () => {
      socket.off('cuecard:shown', onCueCard)
      socket.off('poll:launched', onPollLaunched)
      socket.off('poll:results', onPollResults)
      socket.off('poll:closed', onPollClosed)
      socket.off('quiz:launched', onQuizLaunched)
      socket.off('quiz:next-question', onNextQuestion)
      socket.off('quiz:ended', onQuizEnded)
      socket.off('quiz:score', onQuizScore)
      socket.off('leaderboard:update', onLeaderboard)
      socket.off('notice:pushed', onNotice)
      socket.off('notice:dismissed', onNoticeDismissed)
      socket.off('message:pinned', onPinned)
      socket.off('message:unpinned', onUnpinned)
      socket.off('assignment:unlocked', onAssignmentUnlocked)
      socket.off('raise_hand:up', onHandUp)
      socket.off('raise_hand:down', onHandDown)
      socket.off('session:ended', onSessionEnded)
    }
  }, [sessionId])
}
