"""
app/services/orchestrator.py — the agentic loop for MediTourBuddy.

Retrieve-then-generate: Claude spends phase 1 deciding which registry
tools to call and gathering candidate clinic data; phase 2 is a fresh,
tightly-scoped call that writes the final report from ONLY that gathered
data — not from the (possibly long) phase-1 conversation, which is
discarded after retrieval. This exists because letting one long
conversation both retrieve data AND write the final answer left too much
room for the final write-up to drift from what was actually retrieved
(misremembered prices, clinics slipped in that were never really looked
up). `_ground_report_options` is the server-side backstop on top of that:
even phase 2's answer is verified against `known_clinics`, not trusted
outright.

`run_case` is a pure `CaseIntake -> CaseResult` function with no DB
awareness — `app/routers/cases.py` is what persists `Case`/`Report` rows
around calls to it.
"""

import json
import logging
from typing import Any

from anthropic import AsyncAnthropic
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.mcp_client import mcp_manager
from app.schemas.cases import CaseIntake
from app.schemas.report import Accreditation, DISCLAIMER, ModelReportPayload, PriceUSD, Report, ReportOption

logger = logging.getLogger(__name__)

MAX_ROUNDS = 10  # circuit breaker: hard stop on runaway tool loops in retrieval
MODEL = "claude-sonnet-4-6"
AGENT_TEMPERATURE = 0.2  # factual extraction/ranking, not creative writing

RETRIEVAL_SYSTEM_PROMPT = """\
You are MediTourBuddy, a medical-tourism information coordinator helping a
Canadian patient explore accredited overseas dental clinics. This is the
RETRIEVAL phase only — you are gathering data, not writing the final
report (a separate step does that from what you gather here).

You are NOT a medical advisor. Hard rules:
- Never recommend whether to undergo a procedure. Never interpret symptoms.
- Map the patient's description to a procedure code (list_procedures),
  then search for matching clinics. If the patient gave a budget, ALWAYS
  pass it as max_budget_usd to search_clinics — don't eyeball fit later.
- Inspect the strongest candidates' full profiles (get_clinic_profile) and
  verify their accreditations (verify_accreditation) — a clinic without a
  verified accreditation on file cannot be reported later, so don't bother
  gathering ones you wouldn't stand behind.
- Compare prices against the Canadian quote if one was provided
  (compare_procedures).

Once you've gathered a handful of well-vetted candidates — or concluded
there are none that fit — stop calling tools. Your final message in this
phase is discarded; it does not need to be JSON, a short confirmation is
enough.
"""

GENERATION_SYSTEM_PROMPT = """\
You are MediTourBuddy, writing the final report for a Canadian patient
from a fixed list of already-retrieved, already-verified clinic
candidates. You are NOT a medical advisor — never recommend whether to
undergo a procedure, never interpret symptoms.

You may ONLY select from, rank, and describe the candidates provided below
— never add a clinic, price, or credential that isn't in that list. Rank
by accreditation strength, then price. If the candidate list is empty or
nothing suits the case, return zero options and say so honestly in
case_summary — do not stretch.

Your response must be ONLY a JSON object (no prose, no markdown fences)
with this exact shape:
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


async def _complete(
    client: AsyncAnthropic,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None = None,
) -> Any:
    kwargs: dict[str, Any] = dict(
        model=MODEL,
        max_tokens=4096,
        system=system,
        messages=messages,
        temperature=AGENT_TEMPERATURE,
    )
    if tools is not None:
        kwargs["tools"] = tools
    return await client.messages.create(**kwargs)


# ---- Recording ground truth from tool results (phase 1) ----

def _record_tool_result(
    known_clinics: dict[str, dict[str, Any]],
    tool_name: str,
    args: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Fold one tool call's result into the ground-truth accumulator, keyed
    by clinic slug. This — not the model's memory of the conversation — is
    what phase 2 and the grounding backstop trust."""
    if tool_name == "search_clinics":
        for c in result.get("clinics", []):
            fact = known_clinics.setdefault(c["slug"], {})
            fact["name"], fact["city"], fact["country"] = c["name"], c["city"], c["country"]
            price = c.get("price_range_usd")
            if price:
                fact["price_usd"] = {"min": price["min"], "max": price["max"]}
    elif tool_name == "get_clinic_profile":
        clinic = result.get("clinic")
        if not clinic:
            return
        fact = known_clinics.setdefault(clinic["slug"], {})
        fact["name"], fact["city"], fact["country"] = clinic["name"], clinic["city"], clinic["country"]
        accreditations = result.get("accreditations", [])
        if accreditations:
            fact["accreditations"] = [
                {"body": a["body"], "source_url": a["source_url"], "valid_until": a.get("valid_until")}
                for a in accreditations
            ]
    elif tool_name == "compare_procedures":
        for opt in result.get("options", []):
            fact = known_clinics.setdefault(opt["clinic_slug"], {})
            fact.setdefault("name", opt["clinic_name"])
            price = opt.get("price_range_usd")
            if price:
                fact["price_usd"] = {"min": price["min"], "max": price["max"]}
            fact["savings_vs_quote_pct"] = opt.get("savings_vs_quote_pct")
    elif tool_name == "verify_accreditation":
        slug = args.get("slug")
        if not slug:
            return
        verified = [
            {"body": r["body"], "source_url": r["source_url"], "valid_until": r.get("valid_until")}
            for r in result.get("results", [])
            if r.get("status") == "verified"
        ]
        if verified:
            fact = known_clinics.setdefault(slug, {})
            existing_bodies = {a["body"] for a in fact.get("accreditations", [])}
            fact.setdefault("accreditations", [])
            fact["accreditations"].extend(a for a in verified if a["body"] not in existing_bodies)


# ---- Phase 2 candidate selection ----

def _select_candidates(
    known_clinics: dict[str, dict[str, Any]], budget_usd_max: float | None
) -> list[dict[str, Any]]:
    """Only fully-vetted (priced AND accredited) candidates, budget-filtered
    up front — the model in phase 2 never even sees an option it shouldn't
    be able to report, which is a stronger guarantee than any check applied
    after the fact."""
    candidates: list[dict[str, Any]] = []
    for slug, fact in known_clinics.items():
        price = fact.get("price_usd")
        accreditations = fact.get("accreditations")
        if not price or not accreditations:
            continue
        if budget_usd_max is not None and price["min"] > budget_usd_max:
            continue
        candidates.append(
            {
                "slug": slug,
                "name": fact.get("name"),
                "city": fact.get("city"),
                "country": fact.get("country"),
                "price_usd": price,
                "accreditations": accreditations,
                "savings_vs_quote_pct": fact.get("savings_vs_quote_pct"),
            }
        )
    return candidates


# ---- Grounding backstop on the generated report ----

def _ground_report_options(
    payload: ModelReportPayload,
    known_clinics: dict[str, dict[str, Any]],
    budget_usd_max: float | None,
) -> tuple[ModelReportPayload, list[str]]:
    """Verify — and re-ground, not just validate — the model's chosen
    options against known_clinics. Should rarely catch anything now that
    phase 2 only ever sees pre-filtered candidates; this is the backstop,
    not the primary guarantee."""
    grounded: list[ReportOption] = []
    rejections: list[str] = []
    for opt in payload.options:
        fact = known_clinics.get(opt.clinic.slug)
        if fact is None:
            rejections.append(f"{opt.clinic.slug}: not found in any tool result — dropped")
            continue
        if fact.get("price_usd"):
            opt = opt.model_copy(update={"price_usd": PriceUSD(**fact["price_usd"])})
        if fact.get("accreditations"):
            opt = opt.model_copy(
                update={"accreditations": [Accreditation(**a) for a in fact["accreditations"]]}
            )
        if budget_usd_max is not None and opt.price_usd.min > budget_usd_max:
            rejections.append(
                f"{opt.clinic.slug}: price {opt.price_usd.min} exceeds "
                f"budget_usd_max {budget_usd_max} — dropped"
            )
            continue
        grounded.append(opt)
    return payload.model_copy(update={"options": grounded}), rejections


# ---- The loop ----

async def run_case(intake: CaseIntake) -> CaseResult:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    tools = await _anthropic_tools()
    trace: list[dict[str, Any]] = []
    known_clinics: dict[str, dict[str, Any]] = {}
    input_tokens = 0
    output_tokens = 0

    # ---- Phase 1: retrieval — the model calls tools; we keep the receipts ----
    retrieval_messages: list[dict[str, Any]] = [
        {"role": "user", "content": intake.model_dump_json()}
    ]

    for _round in range(MAX_ROUNDS):
        response = await _complete(client, retrieval_messages, RETRIEVAL_SYSTEM_PROMPT, tools=tools)
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens

        if response.stop_reason != "tool_use":
            break  # final text is discarded — phase 2 writes the real report

        retrieval_messages.append({"role": "assistant", "content": response.content})
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

            if not is_error:
                try:
                    _record_tool_result(known_clinics, block.name, block.input, json.loads(result_text))
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass  # unexpected shape — nothing to ground from this one result, not fatal

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                    "is_error": is_error,
                }
            )
        retrieval_messages.append({"role": "user", "content": tool_results})
    else:
        raise RuntimeError(f"Agent exceeded {MAX_ROUNDS} tool rounds — aborting")

    # ---- Phase 2: generation, from a fresh, tightly-scoped context ----
    # Deliberately NOT a continuation of retrieval_messages — the whole
    # point is writing from the clean candidate list below, not recalling
    # from a (possibly long) tool-calling transcript.
    candidates = _select_candidates(known_clinics, intake.budget_usd_max)
    gen_messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": json.dumps({"intake": intake.model_dump(mode="json"), "candidates": candidates}),
        }
    ]

    response = await _complete(client, gen_messages, GENERATION_SYSTEM_PROMPT)
    input_tokens += response.usage.input_tokens
    output_tokens += response.usage.output_tokens
    last_response_text = "".join(b.text for b in response.content if b.type == "text")
    if not last_response_text:
        raise RuntimeError("Agent produced no final message")

    # Validate; on failure, one retry telling the model exactly what was wrong
    try:
        payload = ModelReportPayload.model_validate(_extract_json(last_response_text))
    except (json.JSONDecodeError, ValidationError) as err:
        gen_messages.append({"role": "assistant", "content": last_response_text})
        gen_messages.append(
            {
                "role": "user",
                "content": (
                    "Your response failed schema validation:\n"
                    f"{err}\n"
                    "Respond again with ONLY the corrected JSON object."
                ),
            }
        )
        retry = await _complete(client, gen_messages, GENERATION_SYSTEM_PROMPT)
        input_tokens += retry.usage.input_tokens
        output_tokens += retry.usage.output_tokens
        last_response_text = "".join(b.text for b in retry.content if b.type == "text")
        payload = ModelReportPayload.model_validate(_extract_json(last_response_text))  # raises → 500, correctly

    # ---- Backstop: verify the generated options against ground truth ----
    payload, rejections = _ground_report_options(payload, known_clinics, intake.budget_usd_max)
    if rejections:
        logger.info("case grounding rejected %d option(s): %s", len(rejections), rejections)
        gen_messages.append({"role": "assistant", "content": last_response_text})
        gen_messages.append(
            {
                "role": "user",
                "content": (
                    "Some options failed verification against the candidates you were given:\n"
                    + "\n".join(f"- {r}" for r in rejections)
                    + "\nRespond again with ONLY corrected JSON — only include candidates from the "
                    "list you were given, each within budget if one was provided."
                ),
            }
        )
        retry = await _complete(client, gen_messages, GENERATION_SYSTEM_PROMPT)
        input_tokens += retry.usage.input_tokens
        output_tokens += retry.usage.output_tokens
        retry_text = "".join(b.text for b in retry.content if b.type == "text")
        try:
            retry_payload = ModelReportPayload.model_validate(_extract_json(retry_text))
            retry_payload, retry_rejections = _ground_report_options(
                retry_payload, known_clinics, intake.budget_usd_max
            )
            if retry_rejections:
                logger.info(
                    "case grounding retry still rejected %d option(s): %s",
                    len(retry_rejections), retry_rejections,
                )
            payload = retry_payload
        except (json.JSONDecodeError, ValidationError):
            pass  # keep the already-grounded first attempt rather than error the whole case

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
