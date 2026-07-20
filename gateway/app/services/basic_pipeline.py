"""
app/services/basic_pipeline.py — the free engine.

Plain async Python, fixed sequence, zero Anthropic tokens, per
meditourbuddy-freemium-spec.md §2.1. Shares `mcp_manager`'s session with
the premium engine (`app/services/orchestrator.py`) but never talks to the
model.
"""

import re
from typing import Any

from app import entitlements
from app.mcp_client import mcp_manager
from app.schemas.cases import CaseIntake
from app.schemas.report import (
    DISCLAIMER,
    Accreditation,
    Clinic,
    PriceUSD,
    ProcedureInfo,
    Report,
    ReportOption,
)

# Deterministic keyword table, most-specific pattern first — e.g.
# "all-on-6" must be checked before the bare "implant" fallback.
_KEYWORD_TABLE: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"all[- ]on[- ]6", re.I), "IMPLANT_ALL_ON_6"),
    (re.compile(r"all[- ]on[- ]4|full arch", re.I), "IMPLANT_ALL_ON_4"),
    (re.compile(r"full mouth (reconstruction|recon)", re.I), "FULL_MOUTH_RECON"),
    (re.compile(r"bone graft", re.I), "BONE_GRAFT"),
    (re.compile(r"sinus lift", re.I), "SINUS_LIFT"),
    (re.compile(r"whitening|whiten", re.I), "TEETH_WHITENING"),
    (re.compile(r"root canal", re.I), "ROOT_CANAL"),
    (re.compile(r"zirconia veneer|veneer.*zirconia", re.I), "VENEER_ZIRCONIA"),
    (re.compile(r"veneer", re.I), "VENEER_EMAX"),
    (re.compile(r"(e-?max|emax) crown|crown.*(e-?max|emax)", re.I), "CROWN_EMAX"),
    (re.compile(r"crown", re.I), "CROWN_ZIRCONIA"),
    (re.compile(r"implant", re.I), "IMPLANT_SINGLE"),
]

BASIC_NEXT_STEPS = [
    "Review the clinics below and their accreditation evidence.",
    "Contact a clinic directly to confirm current pricing and availability.",
    "Upgrade to Premium for a full itinerary and all-in cost estimate.",
]


def match_procedure_code(description: str) -> str | None:
    """Pure, deterministic — no I/O. The router calls this before creating
    a Case row so an unclear description never consumes quota."""
    for pattern, code in _KEYWORD_TABLE:
        if pattern.search(description):
            return code
    return None


def _without_none(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool inputs use Zod `.optional()`, not `.nullable()` — an
    explicit `null` fails validation, so omit unset fields entirely."""
    return {k: v for k, v in args.items() if v is not None}


async def run_basic_case(intake: CaseIntake, procedure_code: str) -> Report:
    country = None if intake.destination_preference == "any" else intake.destination_preference

    search_result = await mcp_manager.call_tool_json(
        "search_clinics",
        _without_none(
            {
                "procedure_code": procedure_code,
                "country": country,
                "max_budget_usd": intake.budget_usd_max,
                "language": intake.language,
                "require_accreditation": True,
            }
        ),
    )
    compare_result = await mcp_manager.call_tool_json(
        "compare_procedures",
        _without_none(
            {
                "procedure_code": procedure_code,
                "canadian_quote_cad": intake.canadian_quote_cad,
                "country": country,
            }
        ),
    )
    savings_by_slug = {
        o["clinic_slug"]: o["savings_vs_quote_pct"] for o in compare_result["options"]
    }

    # search_clinics already ranks accreditation-then-price server-side
    # (search-clinics.ts) — the same rule the premium agent is instructed
    # to use, so tiers never contradict.
    options: list[ReportOption] = []
    for clinic in search_result["clinics"][:3]:
        # search_clinics only returns accreditation body names, not the
        # evidence chain (source_url/valid_until) — fetch the full profile
        # for each shortlisted clinic so every accreditation row still
        # carries a source_url, per the registry's own guardrail.
        profile = await mcp_manager.call_tool_json("get_clinic_profile", {"slug": clinic["slug"]})
        price = clinic["price_range_usd"] or {"min": 0.0, "max": 0.0}
        options.append(
            ReportOption(
                clinic=Clinic(
                    name=clinic["name"],
                    city=clinic["city"],
                    country=clinic["country"],
                    slug=clinic["slug"],
                ),
                accreditations=[
                    Accreditation(
                        body=a["body"], valid_until=a.get("valid_until"), source_url=a["source_url"]
                    )
                    for a in profile["accreditations"]
                ],
                price_usd=PriceUSD(min=price["min"], max=price["max"]),
                savings_vs_quote_pct=savings_by_slug.get(clinic["slug"]),
                trip_notes=None,
                trip_plan=None,
                all_in_cad=None,
            )
        )

    procedure_name = compare_result["procedure"]["name"]
    if options:
        case_summary = (
            f"Based on your description, we matched this to {procedure_name}. "
            f"Here are the top {len(options)} accredited option(s) found, ranked "
            "by accreditation strength and price."
        )
    else:
        case_summary = (
            f"We matched your description to {procedure_name}, but couldn't find "
            "any accredited clinics matching your budget and destination. Try "
            "widening your budget or destination preference."
        )

    return Report(
        report_tier="basic",
        case_summary=case_summary,
        procedure=ProcedureInfo(**compare_result["procedure"]),
        options=options,
        next_steps=BASIC_NEXT_STEPS,
        locked_features=entitlements.locked_features("free"),
        disclaimer=DISCLAIMER,
        trace=None,
    )
