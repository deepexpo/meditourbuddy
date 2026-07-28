"""
Admin visibility into other users and their case history. Same
`_require_admin` gating pattern as routers/mcp.py.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db.models import User
from app.db.session import get_db
from app.errors import AppError
from app.schemas.auth import UserOut
from app.schemas.cases import CaseDetail, CaseListItem
from app.services.case_queries import fetch_case_detail, fetch_cases_for_user

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(current_user: CurrentUser) -> None:
    if not current_user.is_admin:
        raise AppError(403, "Admin access required", "forbidden")


@router.get("/users", response_model=list[UserOut])
async def list_users(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    users = await db.scalars(select(User).order_by(User.created_at.desc()))
    return list(users)


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(404, "User not found", "user_not_found")
    return user


@router.get("/users/{user_id}/cases", response_model=list[CaseListItem])
async def list_user_cases(
    user_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    # No limit — admin sees full history regardless of that user's tier.
    return await fetch_cases_for_user(db, user_id)


@router.get("/users/{user_id}/cases/{case_id}", response_model=CaseDetail)
async def get_user_case(
    user_id: uuid.UUID,
    case_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(current_user)
    detail = await fetch_case_detail(db, user_id, case_id)
    if detail is None:
        raise AppError(404, "Case not found", "case_not_found")
    return detail
