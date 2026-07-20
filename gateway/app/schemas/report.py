"""
The unified Report shape — one schema validated by both the free
(`basic_pipeline`) and premium (`orchestrator`) engines, per
meditourbuddy-freemium-spec.md §3. iOS renders sections by field presence,
not by `report_tier`, so this file is the single source of truth for what
"one shape, both tiers" means.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# Injected by code AFTER validation — never trust the model to include it,
# and the free engine never talks to a model at all.
DISCLAIMER = (
    "Informational only — not medical advice. MediTourBuddy does not "
    "recommend treatments. Verify all details directly with the clinic "
    "and consult your own dentist."
)


class Clinic(BaseModel):
    name: str
    city: str
    country: str
    slug: str


class Accreditation(BaseModel):
    body: str
    valid_until: str | None = None
    source_url: str


class PriceUSD(BaseModel):
    min: float
    max: float


class ProcedureInfo(BaseModel):
    code: str
    name: str
    typical_visits: int
    recovery_days_onsite: int


class ReportOption(BaseModel):
    clinic: Clinic
    accreditations: list[Accreditation]
    price_usd: PriceUSD
    savings_vs_quote_pct: float | None = None
    trip_notes: str | None = None
    # Premium-only, populated once travel-mcp lands — always null on the
    # free tier. Shape isn't finalized yet, hence the untyped dict.
    trip_plan: dict[str, Any] | None = None
    all_in_cad: dict[str, Any] | None = None


class ModelReportPayload(BaseModel):
    """Exactly what the agent's final JSON message must contain — the
    envelope fields (`report_tier`, `locked_features`, `disclaimer`,
    `trace`) are layered on by code afterward, never produced by the model.
    """

    case_summary: str
    procedure: ProcedureInfo
    options: list[ReportOption] = Field(max_length=3)
    next_steps: list[str]


class Report(ModelReportPayload):
    report_tier: Literal["basic", "full"]
    locked_features: list[str] | None = None
    disclaimer: str
    trace: list[dict[str, Any]] | None = None
