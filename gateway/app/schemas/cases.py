import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.report import Report


class CaseIntake(BaseModel):
    description: str
    canadian_quote_cad: float | None = None
    destination_preference: str = "any"  # "TR" | "MX" | "any"
    budget_usd_max: float | None = None
    language: str = "en"
    # Admin-only stakeholder-demo override — lets an admin preview either
    # report shape on demand. Silently ignored for non-admin accounts (see
    # routers/cases.py's effective_tier logic).
    preview_tier: Literal["free", "premium"] | None = None


class CaseListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    created_at: datetime
    completed_at: datetime | None
    failure_reason: str | None


class CaseDetail(CaseListItem):
    intake: dict[str, Any]
    report: Report | None = None
