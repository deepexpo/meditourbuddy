"""
Shared Case/Report query + assembly logic, used by both the self-service
routes (routers/cases.py, scoped to the caller's own user_id and their own
entitlements) and the admin routes (routers/admin.py, any user_id, no
limits) — one join, one CaseDetail assembly, instead of two copies drifting
apart.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Case, Report as ReportRow
from app.schemas.cases import CaseDetail


async def fetch_cases_for_user(
    db: AsyncSession, user_id: uuid.UUID, limit: int | None = None
) -> list[Case]:
    stmt = select(Case).where(Case.user_id == user_id).order_by(Case.created_at.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(await db.scalars(stmt))


async def fetch_case_detail(
    db: AsyncSession, user_id: uuid.UUID, case_id: uuid.UUID
) -> CaseDetail | None:
    case = await db.scalar(select(Case).where(Case.id == case_id, Case.user_id == user_id))
    if case is None:
        return None

    report_row = await db.scalar(select(ReportRow).where(ReportRow.case_id == case.id))
    return CaseDetail(
        id=case.id,
        status=case.status,
        created_at=case.created_at,
        completed_at=case.completed_at,
        failure_reason=case.failure_reason,
        intake=case.intake,
        report=report_row.report if report_row else None,
    )
