import { useState } from 'react'

import { Bookmark as BookmarkIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { useLiveClassStore } from '@/stores/liveClassStore'
import { toast } from '@/stores/toastStore'
import type { Bookmark } from '@/types'

/** Bookmarks mark a moment relative to when the student joined the page. */
export function BookmarkPanel({ sessionId, joinedAt }: { sessionId: string; joinedAt: number }) {
  const bookmarks = useLiveClassStore((s) => s.bookmarks)
  const addBookmark = useLiveClassStore((s) => s.addBookmark)
  const [label, setLabel] = useState('')

  const add = async () => {
    try {
      const created = await api.post<Bookmark>(
        `/api/sessions/${sessionId}/live/bookmarks`,
        { timestampMs: Date.now() - joinedAt, label: label.trim() || null },
      )
      addBookmark(created)
      setLabel('')
    } catch {
      toast({ variant: 'error', title: 'Could not save bookmark' })
    }
  }

  return (
    <div className="space-y-3 p-4">
      <div className="flex gap-2">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Label (optional)"
          className="flex-1 rounded-md bg-white/10 px-3 py-2 text-sm text-white placeholder:text-white/40"
        />
        <Button size="sm" onClick={add}>
          Mark
        </Button>
      </div>
      <div className="space-y-1">
        {bookmarks.length === 0 ? (
          <p className="pt-4 text-center text-sm text-white/50">No bookmarks yet.</p>
        ) : (
          bookmarks.map((b) => (
            <div
              key={b.id}
              className="flex items-center gap-2 rounded-lg bg-white/5 px-3 py-2 text-sm text-white/80"
            >
              <BookmarkIcon size={14} className="text-primary-light" />
              <span className="flex-1 truncate">{b.label ?? 'Bookmark'}</span>
              <span className="text-white/40">{formatMs(b.timestampMs)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function formatMs(ms: number): string {
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}
