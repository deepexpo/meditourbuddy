import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.config import settings


def _validate_password_length(password: str) -> str:
    if len(password) < settings.password_min_length:
        raise ValueError(f"Password must be at least {settings.password_min_length} characters")
    return password


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    # The client shows a consent screen ("informational only — not a
    # medical service provider"); this records that the user agreed. Must
    # be true, not just present.
    consent_accepted: bool

    _validate_password = field_validator("password")(_validate_password_length)

    @field_validator("consent_accepted")
    @classmethod
    def _consent_must_be_accepted(cls, value: bool) -> bool:
        if not value:
            raise ValueError("You must accept the consent terms to register.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequestRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str

    _validate_new_password = field_validator("new_password")(_validate_password_length)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    tier: str
    is_admin: bool
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
