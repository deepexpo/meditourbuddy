"""
app/services/orchestrator.py — the agentic loop for MediTourBuddy.

This is the piece that turns the gateway from an MCP proxy into an agent:
Claude decides which registry tools to call and in what order; this module
executes them via the existing mcp_manager and loops until Claude produces
a final report.

`run_case` is a pure `CaseIntake -> CaseResult` function with no DB
awareness — `app/routers/cases.py` is what persists `Case`/`Report` rows
around calls to it.
"""

import json
from typing import Any

from anthropic import AsyncAnthropic
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.mcp_client import mcp_manager
from app.schemas.cases import CaseIntake
from app.schemas.report import DISCLAIMER, ModelReportPayload, Report

MAX_ROUNDS = 10  # circuit breaker: hard stop on runaway tool loops
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are MediTourBuddy, a medical-tourism information coordinator helping a
Canadian patient explore accredited overseas dental clinics.

You are NOT a medical advisor. Hard rules:
- Never recommend whether to undergo a procedure. Never interpret symptoms.
- Only present clinics returned by your tools. Never invent clinics,
  prices, or credentials.
- Call verify_accreditation for every clinic you include; only include
  clinics whose accreditation status is "verified".
- Rank options by accreditation strength, then price. If nothing fits the
  budget, return zero options and say so honestly — do not stretch.

Process: map the patient's description to a procedure code
(list_procedures), search for matching clinics, inspect the strongest
candidates, verify their accreditations, and compare prices against the
Canadian quote if one was provided.

Your FINAL message must be ONLY a JSON object (no prose, no markdown
fences) with this exact shape:
{
  "case_summary": "<2-3 plain-language sentences>",
  "procedure": {"code": "...", "name": "...", "typical_visits": 0, "recovery_days_onsite": 0},
  "options": [
    {
      "clinic": {"name": "...", "city": "...", "country": "...", "slug": "..."},
      "accreditations": [{"body": "...", "valid_until": null, "source_url": "..."}],
      "price_usd": {"min": 0, "max": 0},
      "savings_vs_quote_pct": null,
      "trip_notes": "<visits required, on-site recovery days>"
    }
  ],
  "next_steps": ["...", "..."]
}
Maximum 3 options.
"""


class CaseResult(BaseModel):
    report: Report
    input_tokens: int
    output_tokens: int


# ---- MCP tools → Anthropic tools format ----

async def _anthropic_tools() -> list[dict[str, Any]]:
    tools = await mcp_manager.list_tools()
    return [
        {
            "name": t["name"],
            "description": t.get("description") or "",
            "input_schema": t.get("inputSchema") or {"type": "object"},
        }
        for t in tools
    ]


def _tool_result_text(content_blocks: list[dict[str, Any]]) -> str:
    """Flatten MCP content blocks to the text Claude sees."""
    return "\n".join(
        b.get("text", "") for b in content_blocks if b.get("type") == "text"
    )


def _extract_json(text: str) -> dict[str, Any]:
    """Parse the model's final message, tolerating stray markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    return json.loads(cleaned)


# ---- The loop ----

async def run_case(intake: CaseIntake) -> CaseResult:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    tools = await _anthropic_tools()
    trace: list[dict[str, Any]] = []
    input_tokens = 0
    output_tokens = 0

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": intake.model_dump_json()}
    ]

    final_text: str | None = None
    for _round in range(MAX_ROUNDS):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens

        if response.stop_reason != "tool_use":
            final_text = "".join(
                b.text for b in response.content if b.type == "text"
            )
            break

        # Execute every tool call in this round via the existing MCP session
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            trace.append({"round": _round, "tool": block.name, "args": block.input})
            try:
                content = await mcp_manager.call_tool(block.name, block.input)
                result_text = _tool_result_text(content)
                is_error = False
            except Exception as exc:  # surface tool failure to the model, keep looping
                result_text = f"Tool execution failed: {exc}"
                is_error = True
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": tool_results})
    else:
        raise RuntimeError(f"Agent exceeded {MAX_ROUNDS} tool rounds — aborting")

    if not final_text:
        raise RuntimeError("Agent produced no final message")

    # Validate; on failure, one retry telling the model exactly what was wrong
    try:
        payload = ModelReportPayload.model_validate(_extract_json(final_text))
    except (json.JSONDecodeError, ValidationError) as err:
        messages.append({"role": "assistant", "content": final_text})
        messages.append(
            {
                "role": "user",
                "content": (
                    "Your response failed schema validation:\n"
                    f"{err}\n"
                    "Respond again with ONLY the corrected JSON object."
                ),
            }
        )
        retry = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        input_tokens += retry.usage.input_tokens
        output_tokens += retry.usage.output_tokens
        retry_text = "".join(b.text for b in retry.content if b.type == "text")
        payload = ModelReportPayload.model_validate(_extract_json(retry_text))  # raises → 500, correctly

    # Envelope fields are injected here, never trusted from the model —
    # same pattern as the disclaimer.
    report = Report(
        report_tier="full",
        disclaimer=DISCLAIMER,
        trace=trace,
        locked_features=None,
        **payload.model_dump(),
    )

    return CaseResult(
        report=report,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
