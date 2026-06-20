/**
 * Opens the socket for a live session and joins its room.
 *
 * Connects on mount, (re)emits `join_session` on every (re)connect so a
 * dropped socket re-enters its rooms automatically, and tears the singleton
 * down on unmount. Cookie auth is handled by the connection (`withCredentials`).
 */

import { useEffect } from 'react'

import { disconnectSocket, getSocket } from '@/lib/socket'

export function useSocket(sessionId: string): void {
  useEffect(() => {
    if (!sessionId) return
    const socket = getSocket()
    const join = () => socket.emit('join_session', { sessionId })

    socket.on('connect', join)
    if (socket.connected) join()
    else socket.connect()

    return () => {
      socket.off('connect', join)
      disconnectSocket()
    }
  }, [sessionId])
}
