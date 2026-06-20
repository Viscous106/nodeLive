import { AlertTriangle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useLiveClassStore } from '@/stores/liveClassStore'

/**
 * CRITICAL notices take over the full screen until dismissed. NORMAL notices
 * are surfaced as toasts (see useSocketEvents) and listed in the Notes panel,
 * so they don't appear here.
 */
export function NoticeOverlay() {
  const notices = useLiveClassStore((s) => s.notices)
  const removeNotice = useLiveClassStore((s) => s.removeNotice)
  const critical = notices.find((n) => n.priority === 'CRITICAL')

  if (!critical) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6">
      <div className="flex max-w-lg flex-col items-center gap-4 rounded-2xl bg-white p-8 text-center shadow-2xl">
        <AlertTriangle className="text-danger" size={40} />
        <p className="text-lg font-semibold text-gray-900">{critical.content}</p>
        <Button onClick={() => removeNotice(critical.id)}>Dismiss</Button>
      </div>
    </div>
  )
}
