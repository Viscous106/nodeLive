/**
 * Streams an AI answer: POST the question, then accumulate `ai:response-chunk`
 * socket events (delivered to the asker's private room) until `ai:response-done`.
 * A 501 means the server has no Anthropic key configured — surfaced as a toast.
 */

import { useEffect, useState } from 'react'

import { api, ApiError } from '@/lib/api'
import { getSocket } from '@/lib/socket'
import { toast } from '@/stores/toastStore'

export function useAiStream(sessionId: string) {
  const [response, setResponse] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)

  useEffect(() => {
    const socket = getSocket()
    const onChunk = (d: { chunk: string }) =>
      setResponse((prev) => prev + d.chunk)
    const onDone = () => setIsStreaming(false)
    socket.on('ai:response-chunk', onChunk)
    socket.on('ai:response-done', onDone)
    return () => {
      socket.off('ai:response-chunk', onChunk)
      socket.off('ai:response-done', onDone)
    }
  }, [])

  const send = async (message: string) => {
    setResponse('')
    setIsStreaming(true)
    try {
      // The POST resolves only after the server finishes streaming, so this
      // also clears the flag if the `ai:response-done` socket event is missed.
      await api.post(`/api/sessions/${sessionId}/live/ai-chat`, { message })
      setIsStreaming(false)
    } catch (err) {
      setIsStreaming(false)
      const msg =
        err instanceof ApiError && err.status === 501
          ? 'AI chat isn’t configured on this server.'
          : 'AI request failed.'
      toast({ variant: 'error', title: msg })
    }
  }

  return { response, isStreaming, send }
}
