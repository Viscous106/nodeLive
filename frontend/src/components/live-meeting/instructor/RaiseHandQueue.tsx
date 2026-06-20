import { Hand } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { getSocket } from '@/lib/socket'
import { useLiveClassStore } from '@/stores/liveClassStore'

/** Instructor view of raised hands, in join order, with a "call on" action. */
export function RaiseHandQueue({ sessionId }: { sessionId: string }) {
  const raisedHands = useLiveClassStore((s) => s.raisedHands)
  const removeRaisedHand = useLiveClassStore((s) => s.removeRaisedHand)

  if (raisedHands.length === 0) return null

  const callOn = (userId: string) => {
    getSocket().emit('raise_hand_down', { sessionId, userId })
    removeRaisedHand(userId)
  }

  return (
    <div className="space-y-2 border-t border-white/10 p-3">
      <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-white/50">
        <Hand size={12} /> Raised hands ({raisedHands.length})
      </p>
      {raisedHands.map((h) => (
        <div
          key={h.userId}
          className="flex items-center justify-between rounded-lg bg-white/5 px-3 py-1.5 text-sm text-white/80"
        >
          <span className="truncate">{h.name ?? h.userId}</span>
          <Button variant="ghost" size="sm" onClick={() => callOn(h.userId)}>
            Call on
          </Button>
        </div>
      ))}
    </div>
  )
}
