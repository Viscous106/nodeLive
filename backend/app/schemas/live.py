"""Live-meeting schemas."""

from app.schemas.auth import CamelModel


class ZoomJoinOut(CamelModel):
    signature: str
    sdk_key: str
    zoom_meeting_id: str
