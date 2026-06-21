"""Auth request/response schemas. JSON is camelCase; Python is snake_case."""

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from pydantic.alias_generators import to_camel

from app.models.user import UserRole


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class SignupIn(CamelModel):
    email: EmailStr
    password: str
    display_name: str
    invite_token: str | None = None


class LoginIn(CamelModel):
    email: EmailStr
    password: str


class UserOut(CamelModel):
    id: str
    email: EmailStr
    display_name: str
    role: UserRole
    avatar_url: str | None = None
    coins: int


class ProfileUpdate(CamelModel):
    display_name: str | None = None
    avatar_url: str | None = None

    @field_validator("avatar_url")
    @classmethod
    def _avatar_must_be_http(cls, v: str | None) -> str | None:
        # Avatar is rendered as an <img src>; only allow http(s) (or clearing it)
        # so a stray "javascript:"/junk value can't be stored.
        if v is None or v == "":
            return v
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("avatar_url must be an http(s) URL")
        return v
