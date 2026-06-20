"""Socket.io room naming for a live session.

session:{id}             — everyone in the class
session:{id}:{userId}    — private (e.g. AI responses, personal quiz score)
session:{id}:instructor  — instructors/host only
"""


def session_room(session_id: str) -> str:
    return f"session:{session_id}"


def private_room(session_id: str, user_id: str) -> str:
    return f"session:{session_id}:{user_id}"


def instructor_room(session_id: str) -> str:
    return f"session:{session_id}:instructor"


def compute_rooms(session_id: str, user_id: str, *, is_privileged: bool) -> list[str]:
    rooms = [session_room(session_id), private_room(session_id, user_id)]
    if is_privileged:
        rooms.append(instructor_room(session_id))
    return rooms
