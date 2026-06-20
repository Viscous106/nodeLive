import { useState } from 'react'

import { Hand, Pin } from 'lucide-react'

import { RaiseHandQueue } from '@/components/live-meeting/instructor/RaiseHandQueue'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { getSocket } from '@/lib/socket'
import { useLiveClassStore } from '@/stores/liveClassStore'
import type { User } from '@/types'

interface Props {
  sessionId: string
  user: User | null
  isInstructor: boolean
}

export function ChatPanel({ sessionId, user, isInstructor }: Props) {
  const pinnedMessage = useLiveClassStore((s) => s.pinnedMessage)

  return (
    <div className="flex h-full flex-col">
      {pinnedMessage && (
        <div className="flex items-start gap-2 border-b border-yellow-500/30 bg-yellow-500/10 p-3 text-sm text-yellow-200">
          <Pin size={14} className="mt-0.5 shrink-0" />
          <span>{pinnedMessage}</span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 text-sm text-white/50">
        <p>AI chat with live transcript context arrives in M5.</p>
      </div>

      {isInstructor ? (
        <InstructorChatControls sessionId={sessionId} />
      ) : (
        <StudentRaiseHand sessionId={sessionId} user={user} />
      )}
    </div>
  )
}

function StudentRaiseHand({ sessionId, user }: { sessionId: string; user: User | null }) {
  const [raised, setRaised] = useState(false)

  const toggle = () => {
    const socket = getSocket()
    if (raised) {
      socket.emit('raise_hand_down', { sessionId })
    } else {
      socket.emit('raise_hand_up', { sessionId, name: user?.displayName })
    }
    setRaised((r) => !r)
  }

  return (
    <div className="border-t border-white/10 p-3">
      <Button
        variant={raised ? 'danger' : 'outline'}
        size="sm"
        className="w-full"
        onClick={toggle}
      >
        <Hand size={14} /> {raised ? 'Lower hand' : 'Raise hand'}
      </Button>
    </div>
  )
}

function InstructorChatControls({ sessionId }: { sessionId: string }) {
  const [pin, setPin] = useState('')
  const [cue, setCue] = useState('')

  const setPinned = async () => {
    if (!pin.trim()) return
    await api.put(`/api/sessions/${sessionId}/live/pinned-message`, {
      message: pin.trim(),
    })
    setPin('')
  }
  const unpin = () => api.delete(`/api/sessions/${sessionId}/live/pinned-message`)

  // Create + immediately show a cue card (broadcasts cuecard:shown).
  const showCue = async () => {
    if (!cue.trim()) return
    const card = await api.post<{ id: string }>(
      `/api/sessions/${sessionId}/live/cue-cards`,
      { content: cue.trim(), displayOrder: 0 },
    )
    await api.patch(`/api/sessions/${sessionId}/live/cue-cards/${card.id}/show`)
    setCue('')
  }

  return (
    <div className="space-y-2 border-t border-white/10 p-3">
      <div className="flex gap-2">
        <input
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          placeholder="Pin a message…"
          className="flex-1 rounded-md bg-white/10 px-3 py-2 text-sm text-white placeholder:text-white/40"
        />
        <Button size="sm" onClick={setPinned}>
          Pin
        </Button>
        <Button variant="ghost" size="sm" onClick={unpin}>
          Unpin
        </Button>
      </div>
      <div className="flex gap-2">
        <input
          value={cue}
          onChange={(e) => setCue(e.target.value)}
          placeholder="Show a cue card…"
          className="flex-1 rounded-md bg-white/10 px-3 py-2 text-sm text-white placeholder:text-white/40"
        />
        <Button size="sm" onClick={showCue}>
          Show
        </Button>
      </div>
      <RaiseHandQueue sessionId={sessionId} />
    </div>
  )
}
