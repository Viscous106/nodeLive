"""Auth request/response schemas. JSON is camelCase; Python is snake_case."""

from pydantic import BaseModel, ConfigDict, EmailStr
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
