"""
Cheap, log-based analytics per meditourbuddy-freemium-spec.md §6.
"cases per tier per day" is a query over the existing cases/users tables;
"PROCEDURE_UNCLEAR rate" is logged where it's raised (routers/cases.py).
This is the one signal with no other source: which locked feature a free
user tapped.
"""

import logging

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])
logger = logging.getLogger(__name__)


class LockedCardTapEvent(BaseModel):
    feature: str


@router.post("/locked-card-tap", status_code=204)
async def locked_card_tap(
    payload: LockedCardTapEvent,
    current_user: CurrentUser = Depends(get_current_user),
):
    logger.info("locked_card_tap feature=%s tier=%s", payload.feature, current_user.tier)
    return Response(status_code=204)
