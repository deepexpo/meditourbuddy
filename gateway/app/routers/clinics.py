"""
Thin typed routes wrapping the clinic-registry MCP tools directly, so
clients get clean JSON without going through /mcp/call (admin/debug only
as of this phase — see routers/mcp.py). Available to any authenticated
user, no tier gate.
"""

from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.mcp_client import mcp_manager
from app.services.procedures_cache import get_procedures

router = APIRouter(tags=["clinics"])


@router.get("/procedures")
async def list_procedures(category: str | None = None, current_user: CurrentUser = Depends(get_current_user)):
    procedures = await get_procedures()
    if category is not None:
        procedures = [p for p in procedures if p["category"] == category]
    return {"procedures": procedures}


@router.get("/clinics/search")
async def search_clinics(
    procedure_code: str,
    country: str | None = None,
    max_budget_usd: float | None = None,
    language: str = "en",
    require_accreditation: bool = True,
    current_user: CurrentUser = Depends(get_current_user),
):
    args = {
        "procedure_code": procedure_code,
        "language": language,
        "require_accreditation": require_accreditation,
    }
    if country is not None:
        args["country"] = country
    if max_budget_usd is not None:
        args["max_budget_usd"] = max_budget_usd
    return await mcp_manager.call_tool_json("search_clinics", args)


@router.get("/clinics/{slug}")
async def get_clinic_profile(slug: str, current_user: CurrentUser = Depends(get_current_user)):
    return await mcp_manager.call_tool_json("get_clinic_profile", {"slug": slug})
