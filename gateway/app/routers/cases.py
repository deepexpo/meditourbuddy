import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import settings
from app.db.models import Case, Report as ReportRow
from app.db.session import get_db
from app.errors import AppError
from app.schemas.cases import CaseDetail, CaseListItem
from app.services.orchestrator import DISCLAIMER, MODEL, CaseIntake, run_case

router = APIRouter(prefix="/cases", tags=["cases"])
logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("", response_model=CaseDetail, status_code=201)
async def create_case(
    intake: CaseIntake,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    case = Case(user_id=user_id, intake=intake.model_dump(mode="json"), status="running")
    db.add(case)
    await db.commit()
    await db.refresh(case)

    started = asyncio.get_event_loop().time()
    try:
        result = await asyncio.wait_for(run_case(intake), timeout=settings.case_timeout_seconds)
    except TimeoutError:
        case.status = "failed"
        case.failure_reason = f"Agent run exceeded {settings.case_timeout_seconds:.0f}s timeout"
        case.completed_at = _now()
        await db.commit()
        logger.info("case %s failed: timeout", case.id)
        raise AppError(504, "Agent run timed out", "case_timeout")
    except Exception as exc:  # noqa: BLE001 - any agent/tool/validation failure
        case.status = "failed"
        case.failure_reason = str(exc)[:2000]
        case.completed_at = _now()
        await db.commit()
        logger.info("case %s failed: %s", case.id, type(exc).__name__)
        raise AppError(502, "Agent failed to produce a report", "case_failed")

    case.status = "complete"
    case.completed_at = _now()
    report_row = ReportRow(
        case_id=case.id,
        report=result.report.model_dump(mode="json"),
        trace=result.trace,
        model=MODEL,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
    db.add(report_row)
    await db.commit()
    await db.refresh(case)
    elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)
    logger.info("case %s complete in %dms (%d/%d tokens)", case.id, elapsed_ms, result.input_tokens, result.output_tokens)

    return CaseDetail(
        id=case.id,
        status=case.status,
        created_at=case.created_at,
        completed_at=case.completed_at,
        failure_reason=case.failure_reason,
        intake=case.intake,
        report=result.report,
        disclaimer=result.disclaimer,
        trace=result.trace,
    )


@router.get("", response_model=list[CaseListItem])
async def list_cases(
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cases = await db.scalars(
        select(Case).where(Case.user_id == user_id).order_by(Case.created_at.desc())
    )
    return list(cases)


@router.get("/{case_id}", response_model=CaseDetail)
async def get_case(
    case_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    case = await db.scalar(
        select(Case).where(Case.id == case_id, Case.user_id == user_id)
    )
    if case is None:
        raise AppError(404, "Case not found", "case_not_found")

    report_row = await db.scalar(select(ReportRow).where(ReportRow.case_id == case.id))
    return CaseDetail(
        id=case.id,
        status=case.status,
        created_at=case.created_at,
        completed_at=case.completed_at,
        failure_reason=case.failure_reason,
        intake=case.intake,
        report=report_row.report if report_row else None,
        disclaimer=DISCLAIMER if report_row else None,
        trace=report_row.trace if report_row else None,
    )


@router.delete("/{case_id}", status_code=204)
async def delete_case(
    case_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    case = await db.scalar(
        select(Case).where(Case.id == case_id, Case.user_id == user_id)
    )
    if case is None:
        raise AppError(404, "Case not found", "case_not_found")
    await db.delete(case)
    await db.commit()
    return Response(status_code=204)
