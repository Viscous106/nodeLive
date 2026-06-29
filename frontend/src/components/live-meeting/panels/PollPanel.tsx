import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { useLiveClassStore } from '@/stores/liveClassStore'
import { toast } from '@/stores/toastStore'
import type { PollResults } from '@/types'

interface Props {
  sessionId: string
  isInstructor: boolean
}

export function PollPanel({ sessionId, isInstructor }: Props) {
  const poll = useLiveClassStore((s) => s.activePoll)
  const results = useLiveClassStore((s) => s.pollResults)
  const [voted, setVoted] = useState(false)

  // Reset the local vote flag whenever a new poll is launched, otherwise a
  // student who voted in a previous poll is shown results immediately and can
  // never vote again (mirrors QuizPanel's per-question reset).
  useEffect(() => {
    setVoted(false)
  }, [poll?.id])

  const vote = async (optionIndex: number) => {
    if (!poll) return
    try {
      await api.post<PollResults>(
        `/api/sessions/${sessionId}/live/polls/${poll.id}/respond`,
        { optionIndex },
      )
      setVoted(true)
    } catch {
      toast({ variant: 'error', title: 'Could not submit vote' })
    }
  }

  if (isInstructor) return <InstructorPoll sessionId={sessionId} />

  if (!poll) {
    return <Empty>No active poll. Your instructor will start one.</Empty>
  }

  const total = results.reduce((n, r) => n + r.count, 0)
  const showResults = voted || poll.status === 'CLOSED'

  return (
    <div className="space-y-3 p-4">
      <p className="font-semibold break-words text-white">{poll.question}</p>
      {poll.options.map((opt, i) => {
        const r = results.find((x) => x.optionIndex === i)
        return showResults ? (
          <div key={i} className="rounded-lg bg-white/5 p-2">
            <div className="mb-1 flex justify-between gap-2 text-sm text-white/80">
              <span className="min-w-0 truncate">{opt}</span>
              <span className="shrink-0">{r?.pct ?? 0}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded bg-white/10">
              <div
                className="h-full bg-primary"
                style={{ width: `${r?.pct ?? 0}%` }}
              />
            </div>
          </div>
        ) : (
          <button
            key={i}
            onClick={() => vote(i)}
            disabled={poll.status === 'CLOSED'}
            className="w-full break-words rounded-lg bg-white/5 p-3 text-left text-sm text-white hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:opacity-50"
          >
            {opt}
          </button>
        )
      })}
      {showResults && (
        <p className="text-xs text-white/50">{total} responses</p>
      )}
    </div>
  )
}

function InstructorPoll({ sessionId }: { sessionId: string }) {
  const poll = useLiveClassStore((s) => s.activePoll)
  const results = useLiveClassStore((s) => s.pollResults)
  const [question, setQuestion] = useState('')
  const [options, setOptions] = useState(['', ''])
  const [pending, setPending] = useState(false)

  const launch = async () => {
    const opts = options.map((o) => o.trim()).filter(Boolean)
    if (!question.trim() || opts.length < 2) {
      toast({ variant: 'error', title: 'Need a question and 2+ options' })
      return
    }
    setPending(true)
    try {
      await api.post(`/api/sessions/${sessionId}/live/polls`, {
        question: question.trim(),
        options: opts,
      })
      setQuestion('')
      setOptions(['', ''])
    } catch {
      toast({ variant: 'error', title: 'Could not launch poll' })
    } finally {
      setPending(false)
    }
  }

  const close = async () => {
    if (!poll) return
    setPending(true)
    try {
      await api.delete(`/api/sessions/${sessionId}/live/polls/${poll.id}/close`)
    } catch {
      toast({ variant: 'error', title: 'Could not close poll' })
    } finally {
      setPending(false)
    }
  }

  if (poll && poll.status === 'OPEN') {
    return (
      <div className="space-y-3 p-4">
        <p className="font-semibold break-words text-white">{poll.question}</p>
        {poll.options.map((opt, i) => {
          const r = results.find((x) => x.optionIndex === i)
          return (
            <div key={i} className="rounded-lg bg-white/5 p-2 text-sm text-white/80">
              <div className="flex justify-between gap-2">
                <span className="min-w-0 truncate">{opt}</span>
                <span className="shrink-0">
                  {r?.count ?? 0} · {r?.pct ?? 0}%
                </span>
              </div>
            </div>
          )
        })}
        <Button variant="danger" size="sm" onClick={close} disabled={pending}>
          Close poll
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-3 p-4">
      <p className="text-sm font-semibold text-white">Launch a poll</p>
      <input
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Question"
        aria-label="Poll question"
        className="w-full rounded-md bg-white/10 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
      />
      {options.map((opt, i) => (
        <input
          key={i}
          value={opt}
          onChange={(e) =>
            setOptions((o) => o.map((v, j) => (j === i ? e.target.value : v)))
          }
          placeholder={`Option ${i + 1}`}
          aria-label={`Poll option ${i + 1}`}
          className="w-full rounded-md bg-white/10 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        />
      ))}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setOptions((o) => [...o, ''])}
        >
          Add option
        </Button>
        <Button size="sm" onClick={launch} disabled={pending}>
          Launch
        </Button>
      </div>
    </div>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center p-6 text-center text-sm text-white/50">
      {children}
    </div>
  )
}
