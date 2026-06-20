import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { useLiveClassStore } from '@/stores/liveClassStore'

interface Props {
  sessionId: string
  isInstructor: boolean
}

/**
 * Notice feed + (instructor) a composer to push notices. Lecture-note uploads
 * land with Dev A's M6 (R2 storage); shown here as a placeholder for now.
 */
export function NotesPanel({ sessionId, isInstructor }: Props) {
  const notices = useLiveClassStore((s) => s.notices)
  const [content, setContent] = useState('')
  const [critical, setCritical] = useState(false)

  const push = async () => {
    if (!content.trim()) return
    await api.post(`/api/sessions/${sessionId}/live/notices`, {
      content: content.trim(),
      priority: critical ? 'CRITICAL' : 'NORMAL',
    })
    setContent('')
    setCritical(false)
  }

  return (
    <div className="space-y-3 p-4">
      {isInstructor && (
        <div className="space-y-2 rounded-lg bg-white/5 p-3">
          <input
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Push a notice…"
            className="w-full rounded-md bg-white/10 px-3 py-2 text-sm text-white placeholder:text-white/40"
          />
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-xs text-white/70">
              <input
                type="checkbox"
                checked={critical}
                onChange={(e) => setCritical(e.target.checked)}
              />
              Critical (full-screen)
            </label>
            <Button size="sm" onClick={push}>
              Push
            </Button>
          </div>
        </div>
      )}

      <p className="text-xs font-medium uppercase tracking-wide text-white/40">
        Notices
      </p>
      {notices.length === 0 ? (
        <p className="text-center text-sm text-white/50">No notices yet.</p>
      ) : (
        notices.map((n) => (
          <div
            key={n.id}
            className="rounded-lg bg-white/5 px-3 py-2 text-sm text-white/80"
          >
            {n.priority === 'CRITICAL' && (
              <span className="mr-1 text-red-400">●</span>
            )}
            {n.content}
          </div>
        ))
      )}

      <p className="pt-2 text-xs text-white/30">
        Lecture notes &amp; recordings appear here after class.
      </p>
    </div>
  )
}
