"""Request/response models for recording playback + watch-tracking."""

from pydantic import BaseModel, Field


class RecordingUrlOut(BaseModel):
    url: str
    expires_in_secs: int


class HeartbeatIn(BaseModel):
    played_from: float = Field(ge=0)
    played_to: float = Field(ge=0)
    duration: float = Field(ge=0)


class ProgressOut(BaseModel):
    last_position_secs: float
    percent_complete: float
    segments: list[list[float]]


class WatchStatusOut(BaseModel):
    available: bool
    percent_complete: float
    last_position_secs: float
    duration_secs: float | None
