import { Download, FileText, Paperclip, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

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
  useDownloadSubmission,
  useGrade,
  useMySubmission,
  useSubmissions,
  useSubmit,
  useUploadUrl,
} from '@/hooks/useAssignments'
import { toast } from '@/stores/toastStore'
import type { Assignment, ClassSession, Submission } from '@/types'

// File submissions store their R2 object key (under this prefix) in `content`;
// text/link submissions store the raw text. Keep this in sync with the backend.
const FILE_PREFIX = 'submissions/'

function fileNameOf(key: string): string {
  return key.split('/').pop() ?? key
}

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
  const getUploadUrl = useUploadUrl(assignment.id)
  const download = useDownloadSubmission()
  const [content, setContent] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const isFileSubmission = submission?.content.startsWith(FILE_PREFIX) ?? false

  useEffect(() => {
    // Don't echo the opaque R2 key into the textarea for file submissions.
    if (submission && !submission.content.startsWith(FILE_PREFIX)) {
      setContent(submission.content)
    }
  }, [submission])

  const graded = submission?.status === 'GRADED'
  const busy = submit.isPending || uploading

  async function handleSubmit() {
    if (file) {
      setUploading(true)
      try {
        const { uploadUrl, fileKey } = await getUploadUrl.mutateAsync({
          filename: file.name,
          contentType: file.type || 'application/octet-stream',
        })
        const put = await fetch(uploadUrl, {
          method: 'PUT',
          body: file,
          headers: { 'Content-Type': file.type || 'application/octet-stream' },
        })
        if (!put.ok) throw new Error(`upload failed: ${put.status}`)
        submit.mutate(fileKey)
        setFile(null)
        if (fileRef.current) fileRef.current.value = ''
      } catch {
        // 501 (storage off) or a failed PUT — tell the user and let them fall
        // back to a link/text submission instead of failing silently.
        toast({
          variant: 'error',
          title: 'File upload failed — submit a link or text instead.',
        })
      } finally {
        setUploading(false)
      }
    } else {
      submit.mutate(content)
    }
  }

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
          <Label htmlFor={`sub-${assignment.id}`}>Your submission</Label>

          {file ? (
            <div className="flex items-center gap-2 rounded-btn border border-border bg-page px-3 py-2">
              <Paperclip className="h-4 w-4 shrink-0 text-text-muted" />
              <span className="min-w-0 flex-1 truncate text-sm text-text-primary">
                {file.name}
              </span>
              <button
                type="button"
                onClick={() => {
                  setFile(null)
                  if (fileRef.current) fileRef.current.value = ''
                }}
                className="text-text-muted hover:text-danger"
                aria-label="Remove file"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <Textarea
              id={`sub-${assignment.id}`}
              rows={3}
              value={isFileSubmission ? '' : content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="https://github.com/you/repo  ·  or type your answer"
            />
          )}

          <input
            ref={fileRef}
            type="file"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) {
                setFile(f)
                setContent('')
              }
            }}
          />

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={handleSubmit} disabled={busy || (!file && !content.trim())}>
              {busy && <Spinner />}
              {submission ? 'Resubmit' : 'Submit'}
            </Button>
            <Button
              variant="outline"
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={busy}
            >
              <Paperclip className="h-4 w-4" />
              Attach file
            </Button>
            {isFileSubmission && (
              <Button
                variant="ghost"
                type="button"
                disabled={download.isPending}
                onClick={() => download.mutate(submission!.id)}
              >
                <Download className="h-4 w-4" />
                {fileNameOf(submission!.content)}
              </Button>
            )}
            {submission?.status === 'SUBMITTED' && !isFileSubmission && (
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
  const download = useDownloadSubmission()
  const [score, setScore] = useState(submission.grade?.toString() ?? '')
  const [feedback, setFeedback] = useState(submission.feedback ?? '')

  return (
    <div className="space-y-2 rounded-btn border border-border p-3">
      {submission.content.startsWith(FILE_PREFIX) ? (
        <button
          type="button"
          disabled={download.isPending}
          onClick={() => download.mutate(submission.id)}
          className="flex items-center gap-1.5 text-sm text-primary underline hover:opacity-80 disabled:opacity-50"
        >
          {download.isPending ? <Spinner /> : <Download className="h-3.5 w-3.5 shrink-0" />}
          {fileNameOf(submission.content)}
        </button>
      ) : submission.content.startsWith('http') ? (
        <a
          href={submission.content}
          target="_blank"
          rel="noopener noreferrer"
          className="break-all text-sm text-primary underline"
        >
          {submission.content}
        </a>
      ) : (
        <p className="break-words text-sm text-text-secondary">
          {submission.content}
        </p>
      )}
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end">
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
