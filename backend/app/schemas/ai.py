"""AI feature schemas."""

from pydantic import Field

from app.schemas.auth import CamelModel


class AiChatIn(CamelModel):
    message: str = Field(min_length=1, max_length=2000)
