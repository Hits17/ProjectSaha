"""Open-roles policy (2026-06-10): creator/manufacturer are signup labels, not
capability boundaries. Marketplace endpoints must be ownership-gated, never
role-gated. Admin/legal remain privileged and non-self-registrable."""

import inspect

from app.api import listings as listings_api
from app.api import materials as materials_api
from app.api import proposals as proposals_api
from app.api.schemas.auth import _SELF_REGISTER_ROLES
from app.db.models.user import UserRole


def _module_source(mod) -> str:
    return inspect.getsource(mod)


def test_listings_have_no_role_gate():
    src = _module_source(listings_api)
    assert "_require_creator" not in src
    assert "UserRole.CREATOR" not in src
    assert "UserRole.MANUFACTURER" not in src


def test_proposals_have_no_role_gate():
    src = _module_source(proposals_api)
    assert "UserRole.CREATOR" not in src
    assert "UserRole.MANUFACTURER" not in src


def test_materials_have_no_role_gate():
    src = _module_source(materials_api)
    assert "UserRole.CREATOR" not in src
    assert "UserRole.MANUFACTURER" not in src


def test_ownership_guards_still_present():
    # Role gates were removed; per-resource ownership checks must remain.
    assert "_require_owner" in _module_source(listings_api)
    assert "require_seller" in _module_source(materials_api)


def test_self_propose_guard_still_present():
    from app.services import proposals as proposals_svc
    assert "Cannot propose on your own listing" in inspect.getsource(proposals_svc)


def test_both_marketplace_roles_can_self_register():
    assert UserRole.CREATOR in _SELF_REGISTER_ROLES
    assert UserRole.MANUFACTURER in _SELF_REGISTER_ROLES


def test_privileged_roles_still_blocked_from_self_register():
    assert UserRole.ADMIN not in _SELF_REGISTER_ROLES
    assert UserRole.LEGAL not in _SELF_REGISTER_ROLES
