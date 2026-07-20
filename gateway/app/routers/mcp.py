from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user
from app.errors import AppError
from app.mcp_client import mcp_manager

router = APIRouter(tags=["mcp"])


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


def _require_admin(current_user: CurrentUser) -> None:
    # Admin/debug only this phase — clients use the typed routes in
    # clinics.py instead (search_clinics, get_clinic_profile, etc.).
    if not current_user.is_admin:
        raise AppError(403, "Admin access required", "forbidden")


@router.get("/mcp/tools")
async def list_tools(current_user: CurrentUser = Depends(get_current_user)):
    _require_admin(current_user)
    return {"tools": await mcp_manager.list_tools()}


@router.post("/mcp/call")
async def call_tool(payload: ToolCallRequest, current_user: CurrentUser = Depends(get_current_user)):
    _require_admin(current_user)
    try:
        result = await mcp_manager.call_tool(payload.name, payload.arguments)
    except Exception as exc:  # noqa: BLE001 - surface MCP errors as 400s
        raise HTTPException(status_code=400, detail=str(exc))
    return {"result": result}
