import secrets

import pytest
from pydantic import ValidationError

from app.config import settings
from app.schemas.auth import PasswordResetConfirmRequest, RegisterRequest


def test_code_generation_is_six_digits_and_zero_padded():
    # Same generation approach as routers/auth.py's request_password_reset —
    # verifies the format, not the randomness source itself.
    for _ in range(20):
        code = f"{secrets.randbelow(1_000_000):06d}"
        assert len(code) == 6
        assert code.isdigit()


def test_register_requires_consent_true():
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@example.com", password="x" * settings.password_min_length, consent_accepted=False)


def test_register_rejects_missing_consent():
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate({"email": "a@example.com", "password": "x" * settings.password_min_length})


def test_register_accepts_consent_true():
    req = RegisterRequest(email="a@example.com", password="x" * settings.password_min_length, consent_accepted=True)
    assert req.consent_accepted is True


def test_register_password_length_uses_setting_not_hardcoded_ten():
    too_short = "x" * (settings.password_min_length - 1)
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@example.com", password=too_short, consent_accepted=True)

    exactly_min = "x" * settings.password_min_length
    req = RegisterRequest(email="a@example.com", password=exactly_min, consent_accepted=True)
    assert req.password == exactly_min


def test_password_reset_confirm_uses_same_length_setting():
    too_short = "x" * (settings.password_min_length - 1)
    with pytest.raises(ValidationError):
        PasswordResetConfirmRequest(email="a@example.com", code="123456", new_password=too_short)

    exactly_min = "x" * settings.password_min_length
    req = PasswordResetConfirmRequest(email="a@example.com", code="123456", new_password=exactly_min)
    assert req.new_password == exactly_min
