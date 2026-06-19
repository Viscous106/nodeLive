import { cn } from '@/lib/utils'

export interface DayTab {
  key: string
  label: string
  dateNum: number
  hasClasses: boolean
}

export function DateTabStrip({
  days,
  selectedKey,
  onSelect,
}: {
  days: DayTab[]
  selectedKey: string
  onSelect: (key: string) => void
}) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
      {days.map((d) => (
        <button
          key={d.key}
          type="button"
          onClick={() => onSelect(d.key)}
          aria-pressed={d.key === selectedKey}
          className={cn(
            'flex min-w-[56px] flex-col items-center rounded-lg border px-3 py-2 transition-colors',
            d.key === selectedKey
              ? 'border-primary bg-primary/5 text-primary'
              : 'border-border text-text-secondary hover:bg-border-muted',
          )}
        >
          <span className="text-xs font-medium">{d.label}</span>
          <span className="text-base font-semibold">{d.dateNum}</span>
          <span
            className={cn(
              'mt-1 h-1 w-1 rounded-full',
              d.hasClasses ? 'bg-primary' : 'bg-transparent',
            )}
            aria-hidden="true"
          />
        </button>
      ))}
    </div>
  )
}
