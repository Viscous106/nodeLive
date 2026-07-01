import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { useLiveClassStore } from '@/stores/liveClassStore'
import { toast } from '@/stores/toastStore'

interface Props {
  sessionId: string
  isInstructor: boolean
}

export function QuizPanel({ sessionId, isInstructor }: Props) {
  const quiz = useLiveClassStore((s) => s.activeQuiz)
  const question = useLiveClassStore((s) => s.activeQuestion)
  const timeLeft = useLiveClassStore((s) => s.timeLeft)
  const lastScore = useLiveClassStore((s) => s.lastScore)
  const [answeredId, setAnsweredId] = useState<string | null>(null)

  useEffect(() => {
    setAnsweredId(null)
  }, [question?.questionId])

  if (isInstructor) return <InstructorQuiz sessionId={sessionId} />

  if (!quiz) return <Empty>No quiz running yet.</Empty>
  if (!question) return <Empty>Get ready — the next question is coming…</Empty>

  const answered = answeredId === question.questionId

  const answer = async (selectedIndex: number) => {
    setAnsweredId(question.questionId)
    try {
      await api.post(`/api/sessions/${sessionId}/live/quiz/${quiz.id}/respond`, {
        questionId: question.questionId,
        selectedIndex,
      })
    } catch {
      // Release the optimistic lock so the student can retry this question.
      setAnsweredId(null)
      toast({ variant: 'error', title: 'Could not submit answer' })
    }
  }

  return (
    <div className="space-y-3 p-4">
      <div className="flex justify-between text-xs text-gray-600">
        <span>Question {question.index + 1}</span>
        <span>{timeLeft}s</span>
      </div>
      <p className="font-semibold break-words text-gray-900">{question.text}</p>
      {question.options.map((opt, i) => (
        <button
          key={i}
          onClick={() => answer(i)}
          disabled={answered}
          className="w-full break-words rounded-lg bg-gray-50 p-3 text-left text-sm text-gray-900 hover:bg-gray-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:opacity-50"
        >
          {opt}
        </button>
      ))}
      {answered && lastScore && (
        <p
          className={`text-sm font-medium ${lastScore.correct ? 'text-success' : 'text-danger'}`}
        >
          {lastScore.correct ? `Correct! +${lastScore.points}` : 'Incorrect'}
        </p>
      )}
      {answered && !lastScore && (
        <p className="text-sm text-gray-600">Answer submitted…</p>
      )}
    </div>
  )
}

interface DraftQuestion {
  text: string
  options: string[]
  correctIndex: number
}

function InstructorQuiz({ sessionId }: { sessionId: string }) {
  const quiz = useLiveClassStore((s) => s.activeQuiz)
  const [title, setTitle] = useState('')
  const [questions, setQuestions] = useState<DraftQuestion[]>([
    { text: '', options: ['', ''], correctIndex: 0 },
  ])
  const [createdQuizId, setCreatedQuizId] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const addQuestion = () =>
    setQuestions((q) => [...q, { text: '', options: ['', ''], correctIndex: 0 }])

  const update = (i: number, patch: Partial<DraftQuestion>) =>
    setQuestions((q) => q.map((v, j) => (j === i ? { ...v, ...patch } : v)))

  const create = async () => {
    const payload = {
      title: title.trim(),
      timeLimitSecs: 30,
      questions: questions
        .filter((q) => q.text.trim() && q.options.filter(Boolean).length >= 2)
        .map((q) => ({
          text: q.text.trim(),
          options: q.options.map((o) => o.trim()).filter(Boolean),
          correctIndex: q.correctIndex,
        })),
    }
    if (!payload.title || payload.questions.length === 0) {
      toast({ variant: 'error', title: 'Add a title and a complete question' })
      return
    }
    setPending(true)
    try {
      const created = await api.post<{ id: string }>(
        `/api/sessions/${sessionId}/live/quiz`,
        payload,
      )
      setCreatedQuizId(created.id)
      toast({ variant: 'success', title: 'Quiz created — launch when ready' })
    } catch {
      toast({ variant: 'error', title: 'Could not create quiz' })
    } finally {
      setPending(false)
    }
  }

  const launch = async () => {
    if (!createdQuizId) return
    setPending(true)
    try {
      await api.post(`/api/sessions/${sessionId}/live/quiz/${createdQuizId}/launch`)
    } catch {
      toast({ variant: 'error', title: 'Could not launch quiz' })
    } finally {
      setPending(false)
    }
  }

  if (quiz && quiz.status === 'LIVE') {
    return (
      <div className="p-4 text-sm text-gray-700">
        <p className="font-semibold text-gray-900">{quiz.title}</p>
        <p className="mt-2 text-gray-600">
          Quiz is live — questions rotate every {quiz.timeLimitSecs}s.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3 p-4">
      <p className="text-sm font-semibold text-gray-900">Build a quiz</p>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Quiz title"
        aria-label="Quiz title"
        className="w-full rounded-md border border-gray-300 bg-gray-100 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
      />
      {questions.map((q, qi) => (
        <div key={qi} className="space-y-2 rounded-lg bg-gray-50 p-2">
          <input
            value={q.text}
            onChange={(e) => update(qi, { text: e.target.value })}
            placeholder={`Question ${qi + 1}`}
            aria-label={`Question ${qi + 1}`}
            className="w-full rounded-md border border-gray-300 bg-gray-100 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          />
          {q.options.map((opt, oi) => (
            <label key={oi} className="flex items-center gap-2">
              <input
                type="radio"
                checked={q.correctIndex === oi}
                onChange={() => update(qi, { correctIndex: oi })}
              />
              <input
                value={opt}
                onChange={(e) =>
                  update(qi, {
                    options: q.options.map((v, j) => (j === oi ? e.target.value : v)),
                  })
                }
                placeholder={`Option ${oi + 1}`}
                aria-label={`Question ${qi + 1} option ${oi + 1}`}
                className="w-full rounded-md border border-gray-300 bg-gray-100 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
              />
            </label>
          ))}
          <button
            onClick={() =>
              update(qi, { options: [...q.options, ''] })
            }
            className="rounded text-xs text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          >
            + option
          </button>
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={addQuestion}>
          Add question
        </Button>
        {createdQuizId ? (
          <Button size="sm" onClick={launch} disabled={pending}>
            Launch quiz
          </Button>
        ) : (
          <Button size="sm" onClick={create} disabled={pending}>
            Create
          </Button>
        )}
      </div>
    </div>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center p-6 text-center text-sm text-gray-500">
      {children}
    </div>
  )
}
