import { useState } from 'react'

import { Hand, Pin, Sparkles } from 'lucide-react'

import { RaiseHandQueue } from '@/components/live-meeting/instructor/RaiseHandQueue'
import { Button } from '@/components/ui/button'
import { useAiStream } from '@/hooks/useAiStream'
import { api } from '@/lib/api'
import { getSocket } from '@/lib/socket'
import { useLiveClassStore } from '@/stores/liveClassStore'
import { toast } from '@/stores/toastStore'
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
          <span className="min-w-0 break-words">{pinnedMessage}</span>
        </div>
      )}

      <div className="min-h-0 flex-1">
        <AiChat sessionId={sessionId} />
      </div>

      {isInstructor ? (
        <InstructorChatControls sessionId={sessionId} />
      ) : (
        <StudentRaiseHand sessionId={sessionId} user={user} />
      )}
    </div>
  )
}

function AiChat({ sessionId }: { sessionId: string }) {
  const { response, isStreaming, send } = useAiStream(sessionId)
  const [question, setQuestion] = useState('')

  const ask = () => {
    const q = question.trim()
    if (!q || isStreaming) return
    send(q)
    setQuestion('')
  }

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4 text-sm">
        {!response && !isStreaming ? (
          <p className="flex items-center gap-2 text-white/40">
            <Sparkles size={14} /> Ask the AI about this lecture — it uses the
            live transcript for context.
          </p>
        ) : (
          <div className="rounded-lg border border-primary/40 bg-primary/10 p-3 text-white/90">
            <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-primary-light">
              <Sparkles size={12} /> AI assistant
            </p>
            <p className="whitespace-pre-wrap">
              {response}
              {isStreaming && <span className="animate-pulse">▋</span>}
            </p>
          </div>
        )}
      </div>
      <div className="flex gap-2 border-t border-white/10 p-3">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && ask()}
          placeholder="Ask the AI…"
          aria-label="Ask the AI a question about this lecture"
          disabled={isStreaming}
          className="min-w-0 flex-1 rounded-md bg-white/10 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:opacity-50"
        />
        <Button size="sm" onClick={ask} disabled={isStreaming}>
          Ask
        </Button>
      </div>
    </div>
  )
}

function StudentRaiseHand({
  sessionId,
  user,
}: {
  sessionId: string
  user: User | null
}) {
  const [raised, setRaised] = useState(false)

  const toggle = () => {
    const socket = getSocket()
    // Don't flip the button optimistically if the socket is down — otherwise it
    // would show "Lower hand" while the instructor never received the raise.
    if (!socket.connected) {
      toast({ variant: 'error', title: 'Not connected — try again' })
      return
    }
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
  const [pinPending, setPinPending] = useState(false)
  const [cuePending, setCuePending] = useState(false)

  const setPinned = async () => {
    if (!pin.trim()) return
    setPinPending(true)
    try {
      await api.put(`/api/sessions/${sessionId}/live/pinned-message`, {
        message: pin.trim(),
      })
      setPin('')
    } catch {
      toast({ variant: 'error', title: 'Could not pin message' })
    } finally {
      setPinPending(false)
    }
  }

  const unpin = async () => {
    setPinPending(true)
    try {
      await api.delete(`/api/sessions/${sessionId}/live/pinned-message`)
    } catch {
      toast({ variant: 'error', title: 'Could not unpin message' })
    } finally {
      setPinPending(false)
    }
  }

  // Create + immediately show a cue card (broadcasts cuecard:shown).
  const showCue = async () => {
    if (!cue.trim()) return
    setCuePending(true)
    try {
      const card = await api.post<{ id: string }>(
        `/api/sessions/${sessionId}/live/cue-cards`,
        { content: cue.trim(), displayOrder: 0 },
      )
      await api.patch(`/api/sessions/${sessionId}/live/cue-cards/${card.id}/show`)
      setCue('')
    } catch {
      toast({ variant: 'error', title: 'Could not show cue card' })
    } finally {
      setCuePending(false)
    }
  }

  return (
    <div className="space-y-2 border-t border-white/10 p-3">
      <div className="flex gap-2">
        <input
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          placeholder="Pin a message…"
          aria-label="Pin a message for everyone"
          className="min-w-0 flex-1 rounded-md bg-white/10 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        />
        <Button size="sm" onClick={setPinned} disabled={pinPending}>
          Pin
        </Button>
        <Button variant="ghost" size="sm" onClick={unpin} disabled={pinPending}>
          Unpin
        </Button>
      </div>
      <div className="flex gap-2">
        <input
          value={cue}
          onChange={(e) => setCue(e.target.value)}
          placeholder="Show a cue card…"
          aria-label="Show a cue card over the video"
          className="min-w-0 flex-1 rounded-md bg-white/10 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        />
        <Button size="sm" onClick={showCue} disabled={cuePending}>
          Show
        </Button>
      </div>
      <RaiseHandQueue sessionId={sessionId} />
    </div>
  )
}
