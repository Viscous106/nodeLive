import { useEffect, useState } from 'react'

import { useLiveClassStore } from '@/stores/liveClassStore'

/**
 * Slides in the most recently shown cue card over the video, then auto-dismisses
 * after 30s. Re-shows whenever a new `cuecard:shown` updates the store.
 */
export function CueCardOverlay() {
  const card = useLiveClassStore((s) => s.currentCueCard)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!card) return
    setVisible(true)
    const t = setTimeout(() => setVisible(false), 30_000)
    return () => clearTimeout(t)
  }, [card])

  if (!card || !visible) return null

  return (
    <div className="absolute bottom-6 left-6 z-20 max-w-[min(24rem,calc(100%-3rem))] rounded-xl bg-white p-4 shadow-2xl">
      <p className="text-base leading-relaxed break-words text-gray-900">{card.content}</p>
      <button
        onClick={() => setVisible(false)}
        className="mt-2 rounded text-xs font-medium text-gray-600 hover:text-gray-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
      >
        Dismiss
      </button>
    </div>
  )
}
