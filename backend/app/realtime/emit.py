"""Broadcast live-meeting events to socket rooms from HTTP routes.

Routes `await` these thin wrappers; the socket.io Redis manager fans the event
out to every API instance, so a client connected to any worker receives it.
Celery tasks run in a separate process and use a write-only manager instead
(see `app.workers.quiz_tasks`).

Routes import the module (`from app.realtime import emit`) and call
`emit.to_session(...)` so tests can monkeypatch these functions on the module.
"""

from app.realtime.rooms import instructor_room, private_room, session_room
from app.realtime.server import sio


async def to_session(session_id: str, event: str, payload: dict) -> None:
    await sio.emit(event, payload, room=session_room(session_id))


async def to_instructors(session_id: str, event: str, payload: dict) -> None:
    await sio.emit(event, payload, room=instructor_room(session_id))


async def to_user(session_id: str, user_id: str, event: str, payload: dict) -> None:
    await sio.emit(event, payload, room=private_room(session_id, user_id))
