"""
In-process cache of `list_procedures` — 1h TTL, per
meditourbuddy-freemium-spec.md §2.1. Used to build the `choices` array on
a PROCEDURE_UNCLEAR 422 and to serve `GET /procedures`. The free tier's
keyword matcher (`app/services/basic_pipeline.py`) is a static table, not
built from this cache.
"""

import asyncio
import time

from app.mcp_client import mcp_manager

_TTL_SECONDS = 3600

_cache: list[dict] | None = None
_cached_at: float = 0.0
_lock = asyncio.Lock()


async def get_procedures() -> list[dict]:
    global _cache, _cached_at
    async with _lock:
        if _cache is not None and (time.monotonic() - _cached_at) < _TTL_SECONDS:
            return _cache
        data = await mcp_manager.call_tool_json("list_procedures", {})
        _cache = data["procedures"]
        _cached_at = time.monotonic()
        return _cache
