import { CalendarPlus, Pencil, Plus, X } from 'lucide-react'
import type { FormEvent } from 'react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import {
  useAdminCourses,
  useAdminSessions,
  useCancelSession,
  useCreateCourse,
  useCreateSession,
  useInstructors,
  useUpdateSession,
} from '@/hooks/useAdmin'
import type { ClassSession, SessionStatus } from '@/types'

const STATUS_BADGE: Record<
  SessionStatus,
  'new' | 'success' | 'default' | 'danger'
> = {
  SCHEDULED: 'new',
  LIVE: 'success',
  ENDED: 'default',
  CANCELLED: 'danger',
}

/** ISO → value for <input type="datetime-local"> in the viewer's local tz. */
function toLocalInput(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`
}

const EMPTY = {
  courseId: '',
  hostId: '',
  title: '',
  scheduledAtLocal: '',
  durationMins: 60,
  zoomMeetingId: '',
}

export function SessionsTab() {
  const { data: sessions, isLoading } = useAdminSessions()
  const { data: courses } = useAdminCourses()
  const { data: instructors } = useInstructors()
  const create = useCreateSession()
  const update = useUpdateSession()
  const cancel = useCancelSession()

  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState({ ...EMPTY })
  const pending = create.isPending || update.isPending

  const courseTitle = (id: string) =>
    courses?.find((c) => c.id === id)?.title ?? id

  function reset() {
    setEditingId(null)
    setForm({ ...EMPTY })
  }

  function startEdit(s: ClassSession) {
    setEditingId(s.id)
    setForm({
      courseId: s.courseId,
      hostId: '',
      title: s.title,
      scheduledAtLocal: toLocalInput(s.scheduledAt),
      durationMins: s.durationMins,
      zoomMeetingId: s.zoomMeetingId ?? '',
    })
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    const scheduledAt = new Date(form.scheduledAtLocal).toISOString()
    const common = {
      title: form.title,
      scheduledAt,
      durationMins: Number(form.durationMins),
      zoomMeetingId: form.zoomMeetingId || null,
    }
    if (editingId) {
      update.mutate({ id: editingId, ...common }, { onSuccess: reset })
    } else {
      create.mutate(
        { courseId: form.courseId, hostId: form.hostId || null, ...common },
        { onSuccess: reset },
      )
    }
  }

  const noCourses = courses && courses.length === 0

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Sessions</CardTitle>
          {sessions && (
            <span className="text-sm text-text-muted">
              {sessions.length} total
            </span>
          )}
        </CardHeader>
        <CardContent className="space-y-2">
          {isLoading && (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          )}
          {sessions?.length === 0 && (
            <p className="py-6 text-center text-sm text-text-muted">
              No sessions yet — schedule one on the right.
            </p>
          )}
          {sessions?.map((s) => {
            const closed = s.status === 'ENDED' || s.status === 'CANCELLED'
            return (
              <div
                key={s.id}
                className="flex items-center gap-3 rounded-lg border border-border px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-text-primary">
                    {s.title}
                  </p>
                  <p className="truncate text-xs text-text-muted">
                    {courseTitle(s.courseId)} ·{' '}
                    {new Date(s.scheduledAt).toLocaleString()} · {s.durationMins}m
                    {s.zoomMeetingId ? ` · Zoom ${s.zoomMeetingId}` : ''}
                  </p>
                </div>
                <Badge variant={STATUS_BADGE[s.status]}>{s.status}</Badge>
                <button
                  type="button"
                  onClick={() => startEdit(s)}
                  disabled={closed}
                  aria-label={`Edit ${s.title}`}
                  className="rounded-btn p-2 text-text-secondary hover:bg-border-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:opacity-40"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => cancel.mutate(s.id)}
                  disabled={closed || cancel.isPending}
                  aria-label={`Cancel ${s.title}`}
                  className="rounded-btn p-2 text-danger hover:bg-danger/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:opacity-40"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )
          })}
        </CardContent>
      </Card>

      <Card className="self-start">
        <CardHeader>
          <CardTitle>{editingId ? 'Edit session' : 'Schedule a session'}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {!editingId && (
            <CourseCreator
              prompt={
                noCourses
                  ? 'No courses yet — create one first, then schedule sessions into it.'
                  : undefined
              }
              onCreated={(id) => setForm((f) => ({ ...f, courseId: id }))}
            />
          )}
          {noCourses ? null : (
            <form onSubmit={onSubmit} className="space-y-3" noValidate>
              <div>
                <Label htmlFor="s-course">Course</Label>
                <select
                  id="s-course"
                  required
                  value={form.courseId}
                  disabled={Boolean(editingId)}
                  onChange={(e) => setForm({ ...form, courseId: e.target.value })}
                  className="h-10 w-full rounded-btn border border-border bg-card px-3 text-sm text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:opacity-60"
                >
                  <option value="" disabled>
                    Select a course…
                  </option>
                  {courses?.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title}
                    </option>
                  ))}
                </select>
              </div>
              {!editingId && (
                <div>
                  <Label htmlFor="s-host">Instructor (host)</Label>
                  <select
                    id="s-host"
                    value={form.hostId}
                    onChange={(e) => setForm({ ...form, hostId: e.target.value })}
                    className="h-10 w-full rounded-btn border border-border bg-card px-3 text-sm text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                  >
                    <option value="">Me (default)</option>
                    {instructors?.map((m) => (
                      <option key={m.userId} value={m.userId}>
                        {m.displayName} ({m.role})
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <Label htmlFor="s-title">Title</Label>
                <Input
                  id="s-title"
                  required
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="Indexes & B-Trees"
                />
              </div>
              <div>
                <Label htmlFor="s-when">Date &amp; time</Label>
                <Input
                  id="s-when"
                  type="datetime-local"
                  required
                  value={form.scheduledAtLocal}
                  onChange={(e) =>
                    setForm({ ...form, scheduledAtLocal: e.target.value })
                  }
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="s-dur">Duration (min)</Label>
                  <Input
                    id="s-dur"
                    type="number"
                    min={1}
                    required
                    value={form.durationMins}
                    onChange={(e) =>
                      setForm({ ...form, durationMins: Number(e.target.value) })
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="s-zoom">Zoom ID</Label>
                  <Input
                    id="s-zoom"
                    value={form.zoomMeetingId}
                    onChange={(e) =>
                      setForm({ ...form, zoomMeetingId: e.target.value })
                    }
                    placeholder="optional"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit" className="flex-1" disabled={pending}>
                  {pending ? (
                    <Spinner />
                  ) : (
                    <CalendarPlus className="h-4 w-4" />
                  )}
                  {editingId ? 'Save changes' : 'Schedule'}
                </Button>
                {editingId && (
                  <Button type="button" variant="outline" onClick={reset}>
                    Cancel
                  </Button>
                )}
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function CourseCreator({
  prompt,
  onCreated,
}: {
  prompt?: string
  onCreated: (courseId: string) => void
}) {
  const createCourse = useCreateCourse()
  const [title, setTitle] = useState('')

  function add(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    createCourse.mutate(title.trim(), {
      onSuccess: (course) => {
        onCreated(course.id)
        setTitle('')
      },
    })
  }

  return (
    <div className="space-y-2 rounded-lg border border-dashed border-border p-3">
      {prompt && <p className="text-sm text-text-muted">{prompt}</p>}
      <form onSubmit={add} className="flex items-end gap-2">
        <div className="flex-1">
          <Label htmlFor="new-course">New course</Label>
          <Input
            id="new-course"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Databases"
          />
        </div>
        <Button type="submit" variant="outline" disabled={createCourse.isPending}>
          {createCourse.isPending ? <Spinner /> : <Plus className="h-4 w-4" />}
          Add
        </Button>
      </form>
    </div>
  )
}
