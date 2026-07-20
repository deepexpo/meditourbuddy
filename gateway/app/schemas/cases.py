import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.services.orchestrator import Report


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
    disclaimer: str | None = None
    trace: list[dict[str, Any]] | None = None
