import type { FormEvent } from 'react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import {
  useAdminCourses,
  useCreateEnrollment,
  useDeleteEnrollment,
  useEnrollments,
  useMembers,
} from '@/hooks/useAdmin'

export function EnrollmentsTab() {
  const { data: courses } = useAdminCourses()
  const { data: members } = useMembers()
  const deleteEnr = useDeleteEnrollment()
  const createEnr = useCreateEnrollment()

  const [filterCourse, setFilterCourse] = useState('')
  const [newUserId, setNewUserId] = useState('')
  const [newCourseId, setNewCourseId] = useState('')

  const { data: enrollments, isLoading } = useEnrollments(filterCourse || undefined)

  function onEnroll(e: FormEvent) {
    e.preventDefault()
    if (!newUserId || !newCourseId) return
    createEnr.mutate(
      { userId: newUserId, courseId: newCourseId },
      {
        onSuccess: () => {
          setNewUserId('')
          setNewCourseId('')
        },
      },
    )
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Enrollments</CardTitle>
          <div className="flex items-center gap-2">
            <Label htmlFor="e-filter" className="text-xs text-text-muted">
              Filter by course
            </Label>
            <select
              id="e-filter"
              value={filterCourse}
              onChange={(e) => setFilterCourse(e.target.value)}
              className="h-8 rounded-btn border border-border bg-card px-2 text-xs text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
            >
              <option value="">All courses</option>
              {courses?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {isLoading && (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}
          {!isLoading && enrollments?.length === 0 && (
            <p className="py-6 text-center text-sm text-text-muted">
              No enrollments found.
            </p>
          )}
          {enrollments?.map((e) => (
            <div
              key={e.id}
              className="flex items-center gap-3 rounded-lg border border-border px-3 py-2"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-text-primary">
                  {e.displayName}
                </p>
                <p className="truncate text-xs text-text-muted">
                  {e.email} · {e.courseTitle}
                </p>
              </div>
              <button
                type="button"
                onClick={() => deleteEnr.mutate(e.id)}
                disabled={deleteEnr.isPending}
                aria-label={`Remove ${e.displayName} from ${e.courseTitle}`}
                className="rounded-btn px-2 py-1 text-xs text-danger hover:bg-danger/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:opacity-40"
              >
                Remove
              </button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className="self-start">
        <CardHeader>
          <CardTitle>Enroll a student</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onEnroll} className="space-y-3">
            <div>
              <Label htmlFor="e-user">Member</Label>
              <select
                id="e-user"
                required
                value={newUserId}
                onChange={(e) => setNewUserId(e.target.value)}
                className="h-10 w-full rounded-btn border border-border bg-card px-3 text-sm text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
              >
                <option value="" disabled>
                  Select a member…
                </option>
                {members?.map((m) => (
                  <option key={m.userId} value={m.userId}>
                    {m.displayName} ({m.role})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="e-course">Course</Label>
              <select
                id="e-course"
                required
                value={newCourseId}
                onChange={(e) => setNewCourseId(e.target.value)}
                className="h-10 w-full rounded-btn border border-border bg-card px-3 text-sm text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
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
            <Button type="submit" className="w-full" disabled={createEnr.isPending}>
              {createEnr.isPending ? <Spinner /> : null}
              Enroll
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
