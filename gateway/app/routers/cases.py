import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import entitlements
from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.db.models import Case, Report as ReportRow
from app.db.session import get_db
from app.errors import AppError
from app.schemas.cases import CaseDetail, CaseIntake, CaseListItem
from app.schemas.report import Report
from app.services import basic_pipeline, procedures_cache
from app.services.orchestrator import MODEL, run_case

router = APIRouter(prefix="/cases", tags=["cases"])
logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("", response_model=CaseDetail, status_code=201)
async def create_case(
    intake: CaseIntake,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await entitlements.check_case_quota(db, current_user.id, current_user.tier)

    # Free tier resolves procedure_code up front — an unclear description
    # never creates a Case row or consumes quota. Premium's agent infers
    # procedure_code itself.
    procedure_code: str | None = None
    if current_user.tier == "free":
        procedure_code = basic_pipeline.match_procedure_code(intake.description)
        if procedure_code is None:
            logger.info("procedure_unclear tier=free description_len=%d", len(intake.description))
            raise AppError(
                422,
                "Could not determine procedure from description",
                "PROCEDURE_UNCLEAR",
                extra={"choices": await procedures_cache.get_procedures()},
            )

    case = Case(user_id=current_user.id, intake=intake.model_dump(mode="json"), status="running")
    db.add(case)
    await db.commit()
    await db.refresh(case)

    started = asyncio.get_event_loop().time()
    try:
        if current_user.tier == "free":
            report: Report = await asyncio.wait_for(
                basic_pipeline.run_basic_case(intake, procedure_code), timeout=settings.case_timeout_seconds
            )
            input_tokens = output_tokens = 0
            model_name = "basic_pipeline"
        else:
            result = await asyncio.wait_for(run_case(intake), timeout=settings.case_timeout_seconds)
            report = result.report
            input_tokens, output_tokens = result.input_tokens, result.output_tokens
            model_name = MODEL
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
        report=report.model_dump(mode="json"),
        trace=report.trace,
        model=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    db.add(report_row)
    await db.commit()
    await db.refresh(case)
    elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)
    logger.info(
        "case %s complete in %dms tier=%s (%d/%d tokens)",
        case.id, elapsed_ms, current_user.tier, input_tokens, output_tokens,
    )

    return CaseDetail(
        id=case.id,
        status=case.status,
        created_at=case.created_at,
        completed_at=case.completed_at,
        failure_reason=case.failure_reason,
        intake=case.intake,
        report=report,
    )


@router.get("", response_model=list[CaseListItem])
async def list_cases(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Case)
        .where(Case.user_id == current_user.id)
        .order_by(Case.created_at.desc())
    )
    limit = entitlements.history_limit(current_user.tier)
    if limit is not None:
        stmt = stmt.limit(limit)
    cases = await db.scalars(stmt)
    return list(cases)


@router.get("/{case_id}", response_model=CaseDetail)
async def get_case(
    case_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    case = await db.scalar(
        select(Case).where(Case.id == case_id, Case.user_id == current_user.id)
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
    )


@router.delete("/{case_id}", status_code=204)
async def delete_case(
    case_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    case = await db.scalar(
        select(Case).where(Case.id == case_id, Case.user_id == current_user.id)
    )
    if case is None:
        raise AppError(404, "Case not found", "case_not_found")
    await db.delete(case)
    await db.commit()
    return Response(status_code=204)
