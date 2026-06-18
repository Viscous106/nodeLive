import { Calendar } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useThisWeek } from '@/hooks/useDashboard'

import { ClassCard } from './ClassCard'
import { DateTabStrip } from './DateTabStrip'
import type { DayTab } from './DateTabStrip'

function dayKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
}

export function TimetableSection() {
  const { data: sessions, isLoading } = useThisWeek()
  const [selected, setSelected] = useState<string>(() => dayKey(new Date()))

  const days: DayTab[] = useMemo(() => {
    const byDay = new Set(
      (sessions ?? []).map((s) => dayKey(new Date(s.scheduledAt))),
    )
    const today = new Date()
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(today)
      d.setDate(today.getDate() + i)
      const key = dayKey(d)
      return {
        key,
        label: d.toLocaleDateString('en-US', { weekday: 'short' }),
        dateNum: d.getDate(),
        hasClasses: byDay.has(key),
      }
    })
  }, [sessions])

  const forDay = (sessions ?? []).filter(
    (s) => dayKey(new Date(s.scheduledAt)) === selected,
  )

  return (
    <section className="space-y-3">
      <h2 className="text-xl font-semibold text-text-primary">Time Table</h2>
      <Card>
        <CardContent className="space-y-4 pt-4">
          <DateTabStrip days={days} selectedKey={selected} onSelect={setSelected} />
          {isLoading ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Skeleton className="h-28" />
              <Skeleton className="h-28" />
            </div>
          ) : forDay.length ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {forDay.map((s) => (
                <ClassCard key={s.id} session={s} />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 py-8 text-center">
              <Calendar className="h-8 w-8 text-text-muted" />
              <p className="text-sm text-text-muted">
                No classes scheduled for this day.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
