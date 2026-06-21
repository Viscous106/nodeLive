import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAdminSessions, useSessionAttendance } from '@/hooks/useAdmin'
import type { ClassSession } from '@/types'

function fmt(secs: number): string {
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function AttendanceTable({ sessionId }: { sessionId: string }) {
  const { data, isLoading } = useSessionAttendance(sessionId)

  if (isLoading) return <Skeleton className="h-40 w-full" />
  if (!data) return null

  const present = data.rows.filter((r) => r.attended).length
  const total = data.rows.length
  const pct = total > 0 ? Math.round((present / total) * 100) : 0

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4 text-sm text-text-secondary">
        <span>
          <strong className="text-text-primary">{present}</strong>/{total} attended
        </span>
        <span>
          Attendance rate: <strong className="text-text-primary">{pct}%</strong>
        </span>
        <span>Duration: {data.durationMins} min</span>
      </div>

      {data.rows.length === 0 ? (
        <p className="text-sm text-text-muted">No enrolled students.</p>
      ) : (
        <div className="overflow-x-auto rounded-card border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-border-muted/40 text-left text-xs font-semibold uppercase tracking-wide text-text-muted">
                <th className="px-4 py-2">Student</th>
                <th className="px-4 py-2">Email</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Time present</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr
                  key={row.userId}
                  className="border-b border-border last:border-0 hover:bg-border-muted/30"
                >
                  <td className="px-4 py-2 font-medium text-text-primary">
                    {row.displayName}
                  </td>
                  <td className="px-4 py-2 text-text-secondary">{row.email}</td>
                  <td className="px-4 py-2">
                    <Badge variant={row.attended ? 'new' : 'default'}>
                      {row.attended ? 'Present' : 'Absent'}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-text-secondary">
                    {row.attended ? fmt(row.presentSeconds) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function AttendanceTab() {
  const { data: sessions, isLoading } = useAdminSessions('ENDED')
  const [selected, setSelected] = useState<string | null>(null)

  if (isLoading) return <Skeleton className="h-64 w-full" />

  const ended = sessions ?? []

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Session Attendance</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <label
              htmlFor="session-select"
              className="text-sm font-medium text-text-secondary"
            >
              Select session
            </label>
            <select
              id="session-select"
              value={selected ?? ''}
              onChange={(e) => setSelected(e.target.value || null)}
              className="rounded-btn border border-border bg-card px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
            >
              <option value="">— choose —</option>
              {ended.map((s: ClassSession) => (
                <option key={s.id} value={s.id}>
                  {s.title} ({new Date(s.scheduledAt).toLocaleDateString()})
                </option>
              ))}
            </select>
          </div>

          {ended.length === 0 && (
            <p className="text-sm text-text-muted">
              No ended sessions yet. Attendance data appears after a session
              concludes.
            </p>
          )}

          {selected && <AttendanceTable sessionId={selected} />}
        </CardContent>
      </Card>
    </div>
  )
}
