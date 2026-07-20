"""
JWT auth + password hashing against the real `users` table.

`sub` holds the user's UUID (as a string); `jti` is a random per-token id
(unused for now — logout works via `sessions_invalidated_at` instead, see
below). `get_current_user` does a minimal DB lookup so a hard-deleted
user's still-valid token is rejected immediately rather than just quietly
matching zero rows in every downstream query, and so a token issued
before the user's last logout (`iat` < `sessions_invalidated_at`) is
rejected too — logout invalidates every session/device at once, since
there's no per-token revocation list.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        # A raw float, not a datetime — PyJWT truncates datetime `iat`/`exp`
        # claims to whole seconds, which would make a token re-issued in the
        # same wall-clock second as a logout ambiguous to order against
        # `sessions_invalidated_at`. A float round-trips through the token
        # with full precision, so ordering is always unambiguous.
        "iat": now.timestamp(),
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> uuid.UUID:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = uuid.UUID(payload.get("sub"))
        issued_at = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise credentials_error

    row = (
        await db.execute(
            select(User.id, User.sessions_invalidated_at).where(User.id == user_id)
        )
    ).first()
    if row is None:
        raise credentials_error
    _, invalidated_at = row
    if invalidated_at is not None and issued_at < invalidated_at:
        raise credentials_error
    return user_id
