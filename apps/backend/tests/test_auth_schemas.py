"""Registration input validation — especially the role allow-list."""

import pytest
from pydantic import ValidationError

from app.api.schemas.auth import RegisterRequest


def _valid(**overrides):
    base = {
        "email": "user@example.com",
        # Must satisfy the policy: >= 12 chars, letters + numbers, not common.
        "password": "correct-horse7-battery",
        "full_name": "Test User",
        "role": "creator",
    }
    base.update(overrides)
    return base


def test_valid_creator_registration():
    req = RegisterRequest(**_valid())
    assert req.role.value == "creator"


def test_valid_manufacturer_registration():
    req = RegisterRequest(**_valid(role="manufacturer"))
    assert req.role.value == "manufacturer"


@pytest.mark.parametrize("role", ["admin", "legal"])
def test_privileged_roles_cannot_self_register(role):
    with pytest.raises(ValidationError):
        RegisterRequest(**_valid(role=role))


def test_password_too_short_rejected():
    with pytest.raises(ValidationError):
        RegisterRequest(**_valid(password="short"))


def test_password_over_72_bytes_rejected():
    # bcrypt silently truncates at 72 bytes — must be rejected up front
    with pytest.raises(ValidationError):
        RegisterRequest(**_valid(password="x" * 73))


def test_password_without_number_rejected():
    with pytest.raises(ValidationError):
        RegisterRequest(**_valid(password="alllettersnodigits"))


def test_common_password_rejected():
    with pytest.raises(ValidationError):
        RegisterRequest(**_valid(password="password123"))


def test_invalid_email_rejected():
    with pytest.raises(ValidationError):
        RegisterRequest(**_valid(email="not-an-email"))


def test_email_normalized_to_lowercase():
    req = RegisterRequest(**_valid(email="  User@Example.COM "))
    assert req.email == "user@example.com"


def test_empty_full_name_rejected():
    with pytest.raises(ValidationError):
        RegisterRequest(**_valid(full_name="   "))
