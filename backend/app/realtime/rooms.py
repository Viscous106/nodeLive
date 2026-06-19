"""Socket.io room naming for a live session.

session:{id}             — everyone in the class
session:{id}:{userId}    — private (e.g. AI responses, personal quiz score)
session:{id}:instructor  — instructors/host only
"""


def compute_rooms(session_id: str, user_id: str, *, is_privileged: bool) -> list[str]:
    rooms = [f"session:{session_id}", f"session:{session_id}:{user_id}"]
    if is_privileged:
        rooms.append(f"session:{session_id}:instructor")
    return rooms
