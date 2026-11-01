"""Self-service profile: KYC identity lock, avatar validation, route wiring."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.schemas.user import ChangePasswordRequest, UpdateProfileRequest
from app.db.models.user import KYCStatus
from app.services.profile import (
    ALLOWED_AVATAR_TYPES,
    MAX_AVATAR_BYTES,
    ensure_identity_mutable,
    validate_avatar,
)


# ── Identity lock ────────────────────────────────────────────────────────────

def test_identity_mutable_before_verification():
    for status in (KYCStatus.PENDING, KYCStatus.IN_REVIEW, KYCStatus.REJECTED):
        ensure_identity_mutable(SimpleNamespace(kyc_status=status))  # must not raise


def test_identity_locked_once_verified():
    with pytest.raises(HTTPException) as exc:
        ensure_identity_mutable(SimpleNamespace(kyc_status=KYCStatus.VERIFIED))
    assert exc.value.status_code == 403


# ── Avatar validation ────────────────────────────────────────────────────────

def test_avatar_accepts_browser_raster_formats():
    for ctype, ext in ALLOWED_AVATAR_TYPES.items():
        assert validate_avatar(ctype, 1024) == ext


def test_avatar_content_type_with_charset_suffix():
    assert validate_avatar("image/png; charset=binary", 1024) == "png"


@pytest.mark.parametrize("ctype", ["image/svg+xml", "image/gif", "text/html", None, ""])
def test_avatar_rejects_non_raster_types(ctype):
    with pytest.raises(HTTPException) as exc:
        validate_avatar(ctype, 1024)
    assert exc.value.status_code == 400


def test_avatar_rejects_oversize():
    with pytest.raises(HTTPException) as exc:
        validate_avatar("image/jpeg", MAX_AVATAR_BYTES + 1)
    assert exc.value.status_code == 413


def test_avatar_rejects_empty():
    with pytest.raises(HTTPException) as exc:
        validate_avatar("image/jpeg", 0)
    assert exc.value.status_code == 400


# ── Schemas ──────────────────────────────────────────────────────────────────

def test_profile_update_is_partial():
    upd = UpdateProfileRequest(full_name="  Ada Lovelace  ")
    assert upd.full_name == "Ada Lovelace"
    assert upd.email is None


def test_profile_update_rejects_blank_name():
    with pytest.raises(ValidationError):
        UpdateProfileRequest(full_name="   ")


def test_profile_update_normalizes_email():
    assert UpdateProfileRequest(email=" Ada@Example.COM ").email == "ada@example.com"


def test_profile_update_rejects_bad_email():
    with pytest.raises(ValidationError):
        UpdateProfileRequest(email="not-an-email")


def test_change_password_enforces_policy():
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="x", new_password="short")


# ── Route wiring ─────────────────────────────────────────────────────────────

def _route_deps(path: str, method: str):
    from app.api.users import router

    for route in router.routes:
        if route.path == path and method in route.methods:
            return [d.call for d in route.dependant.dependencies]
    raise AssertionError(f"route {method} {path} not found")


def test_profile_routes_require_login():
    from app.core.security import get_current_user

    for path, method in [
        ("/api/v1/users/me", "PATCH"),
        ("/api/v1/users/me/password", "POST"),
        ("/api/v1/users/me/avatar", "POST"),
        ("/api/v1/users/me/avatar", "GET"),
        ("/api/v1/users/{user_id}/avatar", "GET"),
    ]:
        assert get_current_user in _route_deps(path, method), f"{method} {path} unprotected"
