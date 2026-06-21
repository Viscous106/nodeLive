import { CheckCircle, Clock, Users, XCircle } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAdminSessions, useSessionAttendance } from '@/hooks/useAdmin'
import { useEffect, useState } from 'react'

function formatTime(seconds: number): string {
  if (seconds === 0) return '—'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

export function AttendanceTab() {
  const { data: sessions, isLoading: sessionsLoading } = useAdminSessions()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const { data: attendees, isLoading: attendeesLoading } = useSessionAttendance(selectedId)

  // Auto-select the first ENDED session on load
  useEffect(() => {
    if (!selectedId && sessions) {
      const ended = sessions.find((s) => s.status === 'ENDED')
      if (ended) setSelectedId(ended.id)
    }
  }, [sessions, selectedId])

  const endedSessions = sessions?.filter(
    (s) => s.status === 'ENDED' || s.status === 'LIVE',
  )

  const attended = attendees?.filter((a) => a.attended).length ?? 0
  const total = attendees?.length ?? 0

  return (
    <div className="space-y-4">
      <div>
        <label
          htmlFor="att-session"
          className="mb-1.5 block text-sm font-medium text-text-primary"
        >
          Session
        </label>
        {sessionsLoading ? (
          <Skeleton className="h-10 w-full max-w-sm" />
        ) : (
          <select
            id="att-session"
            value={selectedId ?? ''}
            onChange={(e) => setSelectedId(e.target.value || null)}
            className="h-10 w-full max-w-sm rounded-btn border border-border bg-card px-3 text-sm text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          >
            <option value="" disabled>
              Select a session…
            </option>
            {endedSessions?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title} — {new Date(s.scheduledAt).toLocaleDateString()}
              </option>
            ))}
          </select>
        )}
        {!sessionsLoading && endedSessions?.length === 0 && (
          <p className="mt-2 text-sm text-text-muted">
            No live or ended sessions yet.
          </p>
        )}
      </div>

      {selectedId && (
        <Card>
          <CardHeader className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Users className="h-4 w-4" />
              Attendance
            </CardTitle>
            {!attendeesLoading && attendees && (
              <span className="text-sm text-text-muted">
                {attended} / {total} attended
              </span>
            )}
          </CardHeader>
          <CardContent>
            {attendeesLoading && (
              <div className="space-y-2">
                {[0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            )}

            {!attendeesLoading && attendees?.length === 0 && (
              <p className="py-6 text-center text-sm text-text-muted">
                No enrolled users for this session.
              </p>
            )}

            {!attendeesLoading && attendees && attendees.length > 0 && (
              <>
                {/* No attendance data at all — Zoom hasn't run the reconcile yet */}
                {attended === 0 && (
                  <p className="mb-3 rounded-md border border-border bg-card px-3 py-2 text-xs text-text-muted">
                    No attendance data yet — the Zoom report may not have been
                    processed. Data appears after the reconcile task runs
                    post-meeting.
                  </p>
                )}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs font-semibold uppercase text-text-muted">
                        <th className="py-2 pr-4">Name</th>
                        <th className="py-2 pr-4">Email</th>
                        <th className="py-2 pr-4">Time present</th>
                        <th className="py-2">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {attendees.map((a) => (
                        <tr key={a.userId} className="hover:bg-border-muted/30">
                          <td className="py-2.5 pr-4 font-medium text-text-primary">
                            {a.displayName}
                          </td>
                          <td className="py-2.5 pr-4 text-text-secondary">
                            {a.email}
                          </td>
                          <td className="py-2.5 pr-4 text-text-secondary">
                            <span className="flex items-center gap-1">
                              <Clock className="h-3.5 w-3.5 opacity-50" />
                              {formatTime(a.presentSeconds)}
                            </span>
                          </td>
                          <td className="py-2.5">
                            {a.attended ? (
                              <Badge
                                variant="success"
                                className="flex w-fit items-center gap-1"
                              >
                                <CheckCircle className="h-3 w-3" />
                                Present
                              </Badge>
                            ) : (
                              <Badge
                                variant="default"
                                className="flex w-fit items-center gap-1"
                              >
                                <XCircle className="h-3 w-3" />
                                Absent
                              </Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
