import { FileText } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/hooks/useAuth'
import {
  useAssignments,
  useCreateAssignment,
  useGrade,
  useMySubmission,
  useSubmissions,
  useSubmit,
} from '@/hooks/useAssignments'
import type { Assignment, ClassSession, Submission } from '@/types'

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    day: 'numeric',
    month: 'short',
  })
}

function AssignmentHeader({ assignment }: { assignment: Assignment }) {
  return (
    <div>
      <h3 className="text-base font-semibold text-text-primary">
        {assignment.title}
      </h3>
      {assignment.description && (
        <p className="mt-1 text-sm text-text-muted">{assignment.description}</p>
      )}
      <p className="mt-1 text-xs text-text-muted">
        Max {assignment.maxPoints} pts
        {assignment.dueAt && ` · due ${fmtDate(assignment.dueAt)}`}
      </p>
    </div>
  )
}

function StudentAssignmentCard({ assignment }: { assignment: Assignment }) {
  const { data: submission } = useMySubmission(assignment.id)
  const submit = useSubmit(assignment.id)
  const [content, setContent] = useState('')

  useEffect(() => {
    if (submission) setContent(submission.content)
  }, [submission])

  const graded = submission?.status === 'GRADED'

  return (
    <Card>
      <CardContent className="space-y-3 pt-4">
        <AssignmentHeader assignment={assignment} />

        {graded && (
          <div className="rounded-btn bg-success-light/15 p-3">
            <p className="text-sm font-semibold text-success">
              Graded: {submission?.grade}/{assignment.maxPoints}
            </p>
            {submission?.feedback && (
              <p className="mt-1 text-sm text-text-secondary">
                {submission.feedback}
              </p>
            )}
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor={`sub-${assignment.id}`}>
            Your submission (link or text)
          </Label>
          <Textarea
            id={`sub-${assignment.id}`}
            rows={3}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="https://github.com/you/repo  ·  or type your answer"
          />
          <div className="flex items-center gap-3">
            <Button
              onClick={() => submit.mutate(content)}
              disabled={!content.trim() || submit.isPending}
            >
              {submit.isPending && <Spinner />}
              {submission ? 'Resubmit' : 'Submit'}
            </Button>
            {submission?.status === 'SUBMITTED' && (
              <span className="text-xs text-text-muted">
                Submitted — awaiting grade
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function GradeRow({
  submission,
  maxPoints,
  assignmentId,
}: {
  submission: Submission
  maxPoints: number
  assignmentId: string
}) {
  const grade = useGrade(assignmentId)
  const [score, setScore] = useState(submission.grade?.toString() ?? '')
  const [feedback, setFeedback] = useState(submission.feedback ?? '')

  return (
    <div className="space-y-2 rounded-btn border border-border p-3">
      <p className="break-words text-sm text-text-secondary">
        {submission.content}
      </p>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:flex-wrap">
        <div className="w-full sm:w-24">
          <Label htmlFor={`g-${submission.id}`}>Score</Label>
          <Input
            id={`g-${submission.id}`}
            type="number"
            min={0}
            max={maxPoints}
            value={score}
            onChange={(e) => setScore(e.target.value)}
          />
        </div>
        <div className="flex-1">
          <Label htmlFor={`f-${submission.id}`}>Feedback</Label>
          <Input
            id={`f-${submission.id}`}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Optional"
          />
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            disabled={score === '' || grade.isPending}
            onClick={() =>
              grade.mutate({
                id: submission.id,
                grade: Number(score),
                feedback: feedback || undefined,
              })
            }
          >
            {grade.isPending && <Spinner />}
            Save
          </Button>
          {submission.status === 'GRADED' && <Badge variant="success">Graded</Badge>}
        </div>
      </div>
    </div>
  )
}

function InstructorAssignmentCard({ assignment }: { assignment: Assignment }) {
  const { data: subs, isLoading } = useSubmissions(assignment.id, true)

  return (
    <Card>
      <CardContent className="space-y-3 pt-4">
        <AssignmentHeader assignment={assignment} />
        <p className="text-sm font-medium text-text-primary">
          Submissions ({subs?.length ?? 0})
        </p>
        {isLoading ? (
          <Skeleton className="h-24" />
        ) : subs && subs.length > 0 ? (
          <div className="space-y-2">
            {subs.map((s) => (
              <GradeRow
                key={s.id}
                submission={s}
                maxPoints={assignment.maxPoints}
                assignmentId={assignment.id}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-muted">No submissions yet.</p>
        )}
      </CardContent>
    </Card>
  )
}

function CreateAssignmentForm({
  courseId,
  sessionId,
}: {
  courseId: string
  sessionId: string
}) {
  const create = useCreateAssignment(sessionId)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [maxPoints, setMaxPoints] = useState('100')
  const [open, setOpen] = useState(false)

  if (!open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        + New assignment
      </Button>
    )
  }

  return (
    <Card>
      <CardContent className="space-y-3 pt-4">
        <div>
          <Label htmlFor="a-title">Title</Label>
          <Input
            id="a-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Build a B-tree"
          />
        </div>
        <div>
          <Label htmlFor="a-desc">Description</Label>
          <Textarea
            id="a-desc"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div className="w-28">
          <Label htmlFor="a-pts">Max points</Label>
          <Input
            id="a-pts"
            type="number"
            min={1}
            value={maxPoints}
            onChange={(e) => setMaxPoints(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <Button
            disabled={!title.trim() || create.isPending}
            onClick={() =>
              create.mutate(
                {
                  courseId,
                  sessionId,
                  title,
                  description: description || undefined,
                  maxPoints: Number(maxPoints) || 100,
                },
                {
                  onSuccess: () => {
                    setTitle('')
                    setDescription('')
                    setMaxPoints('100')
                    setOpen(false)
                  },
                },
              )
            }
          >
            {create.isPending && <Spinner />}
            Create
          </Button>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function AssignmentTab({ session }: { session: ClassSession }) {
  const { user } = useAuth()
  const isInstructor = user?.role === 'INSTRUCTOR' || user?.role === 'ADMIN'
  const { data: assignments, isLoading } = useAssignments(session.id)

  return (
    <div className="space-y-4">
      {isInstructor && (
        <CreateAssignmentForm courseId={session.courseId} sessionId={session.id} />
      )}

      {isLoading ? (
        <Skeleton className="h-40" />
      ) : assignments && assignments.length > 0 ? (
        assignments.map((a) =>
          isInstructor ? (
            <InstructorAssignmentCard key={a.id} assignment={a} />
          ) : (
            <StudentAssignmentCard key={a.id} assignment={a} />
          ),
        )
      ) : (
        <div className="flex flex-col items-center gap-2 rounded-card border border-border bg-card py-10 text-center">
          <FileText className="h-8 w-8 text-text-muted" />
          <p className="text-sm text-text-muted">No assignments for this session yet.</p>
        </div>
      )}
    </div>
  )
}
