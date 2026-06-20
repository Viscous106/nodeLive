/**
 * Socket.io client singleton.
 *
 * One connection per browser tab, shared across all live-meeting features.
 * Created lazily and not auto-connected — call `getSocket().connect()` when
 * entering a live session, and `disconnectSocket()` on leave.
 */

import { io, type Socket } from 'socket.io-client'

// Dev: backend on :8000. Prod: same origin as the served SPA. Override with VITE_SOCKET_URL.
const SOCKET_URL =
  import.meta.env.VITE_SOCKET_URL ??
  (import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin)

let socket: Socket | null = null

export function getSocket(): Socket {
  if (!socket) {
    socket = io(SOCKET_URL, {
      withCredentials: true,
      autoConnect: false,
      transports: ['websocket'],
    })
  }
  return socket
}

export function disconnectSocket(): void {
  socket?.disconnect()
  socket = null
}
