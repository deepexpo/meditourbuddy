import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, get_current_user, hash_password, pwd_context, verify_password
from app.config import settings
from app.db.models import PasswordResetCode, User
from app.db.session import get_db
from app.errors import AppError
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequestRequest,
    RegisterRequest,
    UserOut,
)
from app.services.email import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])

# Hashed once at import time so a login attempt against a non-existent email
# still pays the argon2 cost — avoids leaking account existence via timing.
_DUMMY_HASH = pwd_context.hash("dummy-password-for-timing-safety")


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        consent_accepted_at=datetime.now(timezone.utc),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "An account with this email already exists", "email_taken")
    await db.refresh(user)

    token = create_access_token(user.id, user.tier, user.role)
    return AuthResponse(access_token=token, user=UserOut.model_validate(user, from_attributes=True))


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        pwd_context.verify(payload.password, _DUMMY_HASH)
        raise AppError(401, "Invalid email or password", "invalid_credentials")
    if not verify_password(payload.password, user.password_hash):
        raise AppError(401, "Invalid email or password", "invalid_credentials")

    token = create_access_token(user.id, user.tier, user.role)
    return AuthResponse(access_token=token, user=UserOut.model_validate(user, from_attributes=True))


@router.post("/logout", status_code=204)
async def logout(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, current_user.id)
    user.sessions_invalidated_at = datetime.now(timezone.utc)
    await db.commit()
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
async def get_me(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, current_user.id)
    return UserOut.model_validate(user, from_attributes=True)


@router.post("/password-reset/request", status_code=204)
async def request_password_reset(payload: PasswordResetRequestRequest, db: AsyncSession = Depends(get_db)):
    """Always 204, whether or not the email is registered — same
    anti-enumeration principle as login's identical wrong-password-vs-
    unknown-email error."""
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        return Response(status_code=204)

    window_start = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_count = await db.scalar(
        select(func.count())
        .select_from(PasswordResetCode)
        .where(PasswordResetCode.user_id == user.id, PasswordResetCode.created_at >= window_start)
    )
    if (recent_count or 0) >= settings.password_reset_requests_per_hour:
        # Rate limited — still 204, indistinguishable from success.
        return Response(status_code=204)

    # Only the latest code is ever valid — soft-invalidate (not delete)
    # older unused ones, since deleting them would erase the history the
    # rate-limit count above depends on.
    await db.execute(
        update(PasswordResetCode)
        .where(PasswordResetCode.user_id == user.id, PasswordResetCode.used_at.is_(None))
        .values(used_at=datetime.now(timezone.utc))
    )

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        PasswordResetCode(
            user_id=user.id,
            code_hash=pwd_context.hash(code),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.password_reset_code_ttl_minutes),
        )
    )
    await db.commit()

    await send_password_reset_email(user.email, code)
    return Response(status_code=204)


@router.post("/password-reset/confirm", status_code=204)
async def confirm_password_reset(payload: PasswordResetConfirmRequest, db: AsyncSession = Depends(get_db)):
    invalid_code_error = AppError(400, "Invalid or expired reset code", "invalid_reset_code")

    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        raise invalid_code_error

    now = datetime.now(timezone.utc)
    reset_code = await db.scalar(
        select(PasswordResetCode)
        .where(
            PasswordResetCode.user_id == user.id,
            PasswordResetCode.used_at.is_(None),
            PasswordResetCode.expires_at > now,
        )
        .order_by(PasswordResetCode.created_at.desc())
        .limit(1)
    )
    if reset_code is None:
        raise invalid_code_error

    if not pwd_context.verify(payload.code, reset_code.code_hash):
        reset_code.attempt_count += 1
        if reset_code.attempt_count >= settings.password_reset_max_attempts:
            # Burn the code entirely — even the right code won't work after this.
            reset_code.used_at = now
        await db.commit()
        raise invalid_code_error

    user.password_hash = hash_password(payload.new_password)
    # Reuse the same mechanism POST /auth/logout uses — a password reset
    # correctly kills every other active session too.
    user.sessions_invalidated_at = now
    reset_code.used_at = now
    await db.commit()
    return Response(status_code=204)


@router.delete("/me", status_code=204)
async def delete_me(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, current_user.id)
    await db.delete(user)
    await db.commit()
    return Response(status_code=204)
