import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { ToastVariant } from '@/stores/toastStore'
import { useToastStore } from '@/stores/toastStore'

const ICON = { default: Info, success: CheckCircle2, error: AlertCircle }
const ACCENT: Record<ToastVariant, string> = {
  default: 'border-l-primary text-primary',
  success: 'border-l-success text-success',
  error: 'border-l-danger text-danger',
}

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts)
  const dismiss = useToastStore((s) => s.dismiss)

  return (
    <div
      className="fixed bottom-4 right-4 z-[100] flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2"
      role="region"
      aria-label="Notifications"
    >
      {toasts.map((t) => {
        const Icon = ICON[t.variant]
        return (
          <div
            key={t.id}
            role="status"
            className={cn(
              'flex items-start gap-3 rounded-card border border-l-4 bg-card p-3 shadow-elevated',
              ACCENT[t.variant],
            )}
          >
            <Icon className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-text-primary">{t.title}</p>
              {t.description && (
                <p className="mt-0.5 text-sm text-text-muted">{t.description}</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss notification"
              className="shrink-0 text-text-muted transition-colors hover:text-text-secondary"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
