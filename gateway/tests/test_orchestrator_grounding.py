from app.schemas.report import Clinic, ModelReportPayload, PriceUSD, ProcedureInfo, ReportOption
from app.services.orchestrator import _ground_report_options, _select_candidates

_PROCEDURE = ProcedureInfo(code="IMPLANT_SINGLE", name="Single Dental Implant", typical_visits=2, recovery_days_onsite=3)

_FULLY_VETTED_CLINIC = {
    "name": "Real Clinic",
    "city": "Istanbul",
    "country": "TR",
    "price_usd": {"min": 500.0, "max": 800.0},
    "accreditations": [{"body": "JCI", "source_url": "https://example.com/cert", "valid_until": None}],
}


def _option(slug: str, price_min: float = 500.0) -> ReportOption:
    return ReportOption(
        clinic=Clinic(name="Model's Name", city="Model's City", country="TR", slug=slug),
        accreditations=[],
        price_usd=PriceUSD(min=price_min, max=price_min + 100),
        trip_notes=None,
    )


def _payload(*options: ReportOption) -> ModelReportPayload:
    return ModelReportPayload(
        case_summary="summary", procedure=_PROCEDURE, options=list(options), next_steps=["step"]
    )


# ---- _select_candidates ----

def test_select_candidates_excludes_clinic_missing_price():
    known = {"no-price": {"name": "X", "city": "Y", "country": "TR", "accreditations": [{"body": "JCI", "source_url": "u", "valid_until": None}]}}
    assert _select_candidates(known, budget_usd_max=None) == []


def test_select_candidates_excludes_clinic_missing_accreditation():
    known = {"no-accred": {"name": "X", "city": "Y", "country": "TR", "price_usd": {"min": 500.0, "max": 800.0}}}
    assert _select_candidates(known, budget_usd_max=None) == []


def test_select_candidates_excludes_over_budget_clinic():
    known = {"pricey": _FULLY_VETTED_CLINIC}
    assert _select_candidates(known, budget_usd_max=400.0) == []


def test_select_candidates_includes_fully_vetted_in_budget_clinic():
    known = {"real-clinic": _FULLY_VETTED_CLINIC}
    candidates = _select_candidates(known, budget_usd_max=1000.0)
    assert len(candidates) == 1
    assert candidates[0]["slug"] == "real-clinic"
    assert candidates[0]["price_usd"] == {"min": 500.0, "max": 800.0}


def test_select_candidates_no_budget_set_includes_any_price():
    known = {"real-clinic": _FULLY_VETTED_CLINIC}
    assert len(_select_candidates(known, budget_usd_max=None)) == 1


# ---- _ground_report_options ----

def test_ground_report_options_drops_unknown_clinic():
    payload = _payload(_option("never-looked-up"))
    grounded, rejections = _ground_report_options(payload, known_clinics={}, budget_usd_max=None)
    assert grounded.options == []
    assert len(rejections) == 1
    assert "never-looked-up" in rejections[0]


def test_ground_report_options_overwrites_price_from_known_data_no_rejection():
    known = {"real-clinic": _FULLY_VETTED_CLINIC}
    payload = _payload(_option("real-clinic", price_min=999.0))  # model misremembered the price
    grounded, rejections = _ground_report_options(payload, known, budget_usd_max=None)
    assert rejections == []
    assert len(grounded.options) == 1
    assert grounded.options[0].price_usd.min == 500.0  # overwritten with ground truth, not 999.0


def test_ground_report_options_drops_option_over_budget():
    known = {"real-clinic": _FULLY_VETTED_CLINIC}  # price_usd.min = 500.0
    payload = _payload(_option("real-clinic"))
    grounded, rejections = _ground_report_options(payload, known, budget_usd_max=400.0)
    assert grounded.options == []
    assert len(rejections) == 1
    assert "500.0" in rejections[0] and "400" in rejections[0]


def test_ground_report_options_keeps_option_within_budget():
    known = {"real-clinic": _FULLY_VETTED_CLINIC}  # price_usd.min = 500.0
    payload = _payload(_option("real-clinic"))
    grounded, rejections = _ground_report_options(payload, known, budget_usd_max=1000.0)
    assert rejections == []
    assert len(grounded.options) == 1


def test_ground_report_options_no_budget_set_skips_budget_check():
    known = {"real-clinic": _FULLY_VETTED_CLINIC}
    payload = _payload(_option("real-clinic", price_min=50_000.0))
    grounded, rejections = _ground_report_options(payload, known, budget_usd_max=None)
    # Price still gets overwritten to ground truth (500.0), but nothing is
    # rejected purely for being "expensive" when no budget was given.
    assert rejections == []
    assert grounded.options[0].price_usd.min == 500.0
