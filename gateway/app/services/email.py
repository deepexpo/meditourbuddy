"""
The only file that knows about Resend — mirrors how app/mcp_client.py is
the only file that knows about MCP. Swap providers by rewriting this file
alone; nothing else imports httpx or knows the Resend API shape.
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_RESEND_API_URL = "https://api.resend.com/emails"


async def send_password_reset_email(to_email: str, code: str) -> None:
    """Best-effort — logs and swallows failures rather than raising.

    A Resend outage must not turn into a 500 on
    POST /auth/password-reset/request, which would leak "this email exists"
    via an error response that never happens for unknown emails.
    """
    if not settings.resend_api_key:
        logger.warning("resend_api_key not configured — skipping password reset email")
        return

    payload = {
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": "Your MediTourBuddy password reset code",
        "text": (
            f"Your password reset code is {code}.\n\n"
            f"This code expires in {settings.password_reset_code_ttl_minutes} minutes. "
            "If you didn't request this, you can safely ignore this email."
        ),
    }
    headers = {"Authorization": f"Bearer {settings.resend_api_key}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(_RESEND_API_URL, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:  # noqa: BLE001 - best-effort, never propagate
        logger.error("failed to send password reset email: %s", exc)
