from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, get_current_user, hash_password, pwd_context, verify_password
from app.db.models import User
from app.db.session import get_db
from app.errors import AppError
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

# Hashed once at import time so a login attempt against a non-existent email
# still pays the argon2 cost — avoids leaking account existence via timing.
_DUMMY_HASH = pwd_context.hash("dummy-password-for-timing-safety")


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "An account with this email already exists", "email_taken")
    await db.refresh(user)

    token = create_access_token(user.id, user.tier, user.is_admin)
    return AuthResponse(access_token=token, user=UserOut.model_validate(user, from_attributes=True))


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        pwd_context.verify(payload.password, _DUMMY_HASH)
        raise AppError(401, "Invalid email or password", "invalid_credentials")
    if not verify_password(payload.password, user.password_hash):
        raise AppError(401, "Invalid email or password", "invalid_credentials")

    token = create_access_token(user.id, user.tier, user.is_admin)
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


@router.delete("/me", status_code=204)
async def delete_me(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, current_user.id)
    await db.delete(user)
    await db.commit()
    return Response(status_code=204)
