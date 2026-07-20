"""
All tier logic lives here — nowhere else. Changing the free/premium line
(quota numbers, history depth, which report sections are locked) is a
one-file change per meditourbuddy-freemium-spec.md §8.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Case
from app.errors import AppError

FREE_DAILY_CASE_LIMIT = 10
PREMIUM_MONTHLY_AGENT_LIMIT = 10
FREE_HISTORY_LIMIT = 1

LOCKED_FEATURES_FREE = ["custom_plan", "trip_plan", "all_in_cost", "agent_analysis"]


def quota_limit(tier: str) -> int:
    return FREE_DAILY_CASE_LIMIT if tier == "free" else PREMIUM_MONTHLY_AGENT_LIMIT


def is_over_quota(count: int, tier: str) -> bool:
    return count >= quota_limit(tier)


def _quota_window_start(tier: str, now: datetime) -> datetime:
    if tier == "free":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def check_case_quota(db: AsyncSession, user_id: uuid.UUID, tier: str) -> None:
    window_start = _quota_window_start(tier, datetime.now(timezone.utc))
    count = await db.scalar(
        select(func.count())
        .select_from(Case)
        .where(Case.user_id == user_id, Case.created_at >= window_start)
    )
    if is_over_quota(count or 0, tier):
        raise AppError(429, "Quota exceeded for your tier", "QUOTA_EXCEEDED")


def history_limit(tier: str) -> int | None:
    return FREE_HISTORY_LIMIT if tier == "free" else None


def locked_features(tier: str) -> list[str] | None:
    return LOCKED_FEATURES_FREE if tier == "free" else None
