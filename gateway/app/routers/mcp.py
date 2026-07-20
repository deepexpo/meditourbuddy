from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_user
from app.mcp_client import mcp_manager

router = APIRouter(tags=["mcp"])


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


@router.get("/mcp/tools")
async def list_tools(user_id=Depends(get_current_user)):
    return {"tools": await mcp_manager.list_tools()}


@router.post("/mcp/call")
async def call_tool(payload: ToolCallRequest, user_id=Depends(get_current_user)):
    try:
        result = await mcp_manager.call_tool(payload.name, payload.arguments)
    except Exception as exc:  # noqa: BLE001 - surface MCP errors as 400s
        raise HTTPException(status_code=400, detail=str(exc))
    return {"result": result}
