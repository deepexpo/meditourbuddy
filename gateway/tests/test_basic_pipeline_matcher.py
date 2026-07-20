import pytest

from app.services.basic_pipeline import match_procedure_code


@pytest.mark.parametrize(
    "description,expected_code",
    [
        ("I need a single dental implant", "IMPLANT_SINGLE"),
        ("Looking for all-on-4 implants", "IMPLANT_ALL_ON_4"),
        ("I want a full arch of implants", "IMPLANT_ALL_ON_4"),
        ("interested in all-on-6", "IMPLANT_ALL_ON_6"),
        ("I want veneers", "VENEER_EMAX"),
        ("zirconia veneers please", "VENEER_ZIRCONIA"),
        ("need a crown", "CROWN_ZIRCONIA"),
        ("e-max crown for my molar", "CROWN_EMAX"),
        ("I think I need a root canal", "ROOT_CANAL"),
        ("full mouth reconstruction needed", "FULL_MOUTH_RECON"),
        ("bone graft before implants", "BONE_GRAFT"),
        ("sinus lift procedure", "SINUS_LIFT"),
        ("just want teeth whitening", "TEETH_WHITENING"),
    ],
)
def test_match_procedure_code_known_descriptions(description, expected_code):
    assert match_procedure_code(description) == expected_code


def test_match_procedure_code_unclear_description_returns_none():
    assert match_procedure_code("asdkjasdkjasd nothing dental here") is None


def test_match_procedure_code_all_on_6_takes_priority_over_bare_implant():
    # "implant" alone would fall through to IMPLANT_SINGLE — the arch
    # qualifier must win.
    assert match_procedure_code("all-on-6 implant surgery") == "IMPLANT_ALL_ON_6"
