/**
 * Socket.io client singleton.
 *
 * One connection per browser tab, shared across all live-meeting features.
 * Created lazily and not auto-connected — call `getSocket().connect()` when
 * entering a live session, and `disconnectSocket()` on leave.
 */

import { io, type Socket } from 'socket.io-client'

const SOCKET_URL = import.meta.env.VITE_SOCKET_URL ?? 'http://localhost:8000'

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
