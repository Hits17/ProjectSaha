"""Behavioral checks for private references, collaboration policy and E2EE cutover.

Provider operations are mocked. These do not certify the external Matrix client;
the two-device deployment acceptance checks remain mandatory.
"""
import copy
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.schemas.institution import InstitutionCreate, InstitutionResponse, VerificationRequest, VerificationReview
from app.api.schemas.project import ProjectCreate, TaskUpdate
from app.core.config import settings
from app.core.security import require_collaborator
from app.db.models.community import CommunityVisibility, MembershipRole
from app.db.models.user import KYCStatus, UserRole
from app.integrations import matrix
from app.services import communities, institutions, messages


def user(**changes):
    fields = dict(id=uuid.uuid4(), email_verified=True, kyc_status=KYCStatus.PENDING,
                  role=UserRole.CREATOR, mfa_enabled=False)
    fields.update(changes)
    return SimpleNamespace(**fields)


@pytest.mark.parametrize("email,kyc,allowed", [(True, KYCStatus.PENDING, True), (False, KYCStatus.VERIFIED, True), (False, KYCStatus.PENDING, False)])
async def test_open_collaboration_does_not_require_financial_kyc(email, kyc, allowed):
    actor = user(email_verified=email, kyc_status=kyc)
    if allowed:
        assert await require_collaborator(actor) is actor
    else:
        with pytest.raises(HTTPException) as exc:
            await require_collaborator(actor)
        assert exc.value.status_code == 403


async def test_private_space_reference_is_owner_only_not_ordinary_member_or_moderator():
    owner = user()
    space = SimpleNamespace(created_by=owner.id)
    await institutions.require_space_admin(None, space, owner)
    for _role in (MembershipRole.MEMBER, MembershipRole.MODERATOR):
        with pytest.raises(HTTPException) as exc:
            await institutions.require_space_admin(None, space, user())
        assert exc.value.status_code == 403


async def test_platform_admin_still_needs_mfa_to_see_private_reference(monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_ADMIN_MFA", True)
    space = SimpleNamespace(created_by=uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        await institutions.require_space_admin(None, space, user(role=UserRole.ADMIN))
    assert exc.value.status_code == 403
    await institutions.require_space_admin(None, space, user(role=UserRole.ADMIN, mfa_enabled=True))


def test_public_institution_serialization_cannot_leak_private_reference_or_evidence():
    now = datetime.now(timezone.utc)
    public = InstitutionResponse.model_validate(SimpleNamespace(
        id=uuid.uuid4(), name="Open research lab", slug="open-research-lab", description="Open experiments",
        topic="general", visibility=CommunityVisibility.PUBLIC, created_by=uuid.uuid4(),
        created_at=now, updated_at=now, is_institution=True, website_url=None,
        verification_status="pending", reference="SP-PRIVATE", request_note="private evidence",
        evidence_url="https://example.invalid/private", review_note="internal review",
    )).model_dump()
    assert {"reference", "request_note", "evidence_url", "review_note", "reviewed_by"}.isdisjoint(public)
    assert "SP-PRIVATE" not in str(public)


def test_reference_is_unique_and_contains_no_personal_information():
    refs = {institutions.new_reference() for _ in range(100)}
    assert len(refs) == 100
    assert all(ref.startswith("SP-") and len(ref) == 35 for ref in refs)


@pytest.mark.parametrize("url", ["javascript:alert(1)", "http://example.org", "https://user:password@example.org"])
def test_institution_links_reject_unsafe_or_credentialed_urls(url):
    with pytest.raises(ValidationError):
        InstitutionCreate(name="Research Lab", topic="general", website_url=url)


def test_verification_evidence_and_reasons_cannot_be_blank():
    with pytest.raises(ValidationError):
        VerificationRequest(note=" " * 20)
    with pytest.raises(ValidationError):
        VerificationReview(decision="verified", reason=" " * 20)


async def test_disabled_verification_policy_never_auto_approves():
    db = SimpleNamespace(get=AsyncMock(return_value=None), commit=AsyncMock())
    space = SimpleNamespace(id=uuid.uuid4(), verification_status="unverified")
    with pytest.raises(HTTPException) as exc:
        await institutions.request_verification(db, space, "We represent this lab", None)
    assert exc.value.status_code == 409
    assert space.verification_status == "unverified"
    db.commit.assert_not_awaited()


async def test_identity_change_invalidates_verification_even_through_community_route():
    space = SimpleNamespace(id=uuid.uuid4(), is_institution=True, name="Original lab", description=None, website_url="https://original.invalid", verification_status="verified", visibility=CommunityVisibility.PUBLIC)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one=lambda: space)), commit=AsyncMock(), refresh=AsyncMock())
    result = await communities.update_community(db, space, {"name": "Different institution"})
    assert result.verification_status == "unverified"
    assert result.name == "Different institution"


async def test_institution_cannot_be_made_private_through_generic_space_editor():
    space = SimpleNamespace(id=uuid.uuid4(), is_institution=True, visibility=CommunityVisibility.PUBLIC)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one=lambda: space)), commit=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await communities.update_community(db, space, {"visibility": CommunityVisibility.PRIVATE})
    assert exc.value.status_code == 422
    db.commit.assert_not_awaited()


@pytest.mark.parametrize("transport", ["community_write", "community_read", "proposal_write", "proposal_read"])
async def test_legacy_transports_do_not_read_decrypt_or_store_plaintext(transport):
    db = SimpleNamespace(get=AsyncMock(), execute=AsyncMock(), commit=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        if transport == "community_write":
            await communities.post_message(db, None, uuid.uuid4(), "private message")
        elif transport == "community_read":
            await communities.get_messages(db, uuid.uuid4())
        elif transport == "proposal_write":
            await messages.send_message(db, None, uuid.uuid4(), "private message")
        else:
            await messages.get_messages(db, None, uuid.uuid4())
    assert exc.value.status_code == 410
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.fixture
def matrix_settings(monkeypatch):
    for key, value in {
        "MATRIX_HOMESERVER_URL": "https://matrix.example.invalid", "ELEMENT_WEB_URL": "https://chat.example.invalid",
        "MATRIX_SERVER_NAME": "matrix.example.invalid", "MATRIX_SERVICE_USER_ID": "@saha-service:matrix.example.invalid",
        "MATRIX_SERVICE_ACCESS_TOKEN": "test-service-token",
    }.items():
        monkeypatch.setattr(settings, key, value)


def state_events():
    config = matrix.room_configuration("community", "test-space")
    return [{"type": "m.room.create", "state_key": "", "sender": settings.MATRIX_SERVICE_USER_ID, "content": {}}] + config["initial_state"] + [{"type": "m.room.power_levels", "state_key": "", "content": config["power_level_content_override"]}]


def test_encrypted_rooms_disallow_plaintext_and_member_invites(matrix_settings):
    config = matrix.room_configuration("community", "test-space")
    assert config["visibility"] == "private"
    assert config["creation_content"]["m.federate"] is False
    levels = config["power_level_content_override"]
    assert levels["events"]["m.room.encrypted"] == 0
    assert levels["events"]["m.room.message"] == 100
    assert levels["invite"] == 100
    assert "reference" not in str(config)


async def test_room_policy_is_verified_before_returning_a_chat_link(matrix_settings, monkeypatch):
    mocked = AsyncMock(return_value=state_events())
    monkeypatch.setattr(matrix, "call", mocked)
    await matrix.inspect_room("!room:matrix.example.invalid", "community", "test-space")
    mocked.assert_awaited_once()
    assert mocked.call_args.args[1].endswith("/state")


@pytest.mark.parametrize("device_keys,allowed", [({}, True), ({"accidental-device": {"keys": {"curve25519:accidental-device": "public-key"}}}, False)])
async def test_membership_bot_with_crypto_keys_cannot_open_rooms(matrix_settings, monkeypatch, device_keys, allowed):
    mocked = AsyncMock(side_effect=[{"user_id": settings.MATRIX_SERVICE_USER_ID}, {"device_keys": {settings.MATRIX_SERVICE_USER_ID: device_keys}, "failures": {}}])
    monkeypatch.setattr(matrix, "call", mocked)
    if allowed:
        await matrix.assert_keyless_service_account()
    else:
        with pytest.raises(HTTPException) as exc:
            await matrix.assert_keyless_service_account()
        assert exc.value.status_code == 503


@pytest.mark.parametrize("event_type,field,value", [
    ("m.room.encryption", "algorithm", "plaintext"),
    ("m.room.join_rules", "join_rule", "public"),
    ("m.room.history_visibility", "history_visibility", "world_readable"),
    ("m.room.power_levels", "invite", 0),
])
async def test_unsafe_room_state_fails_closed(matrix_settings, monkeypatch, event_type, field, value):
    events = copy.deepcopy(state_events())
    next(e for e in events if e["type"] == event_type)["content"][field] = value
    monkeypatch.setattr(matrix, "call", AsyncMock(return_value=events))
    with pytest.raises(HTTPException) as exc:
        await matrix.inspect_room("!room:matrix.example.invalid", "community", "test-space")
    assert exc.value.status_code == 409


async def test_member_removal_fails_closed_if_external_access_cannot_be_revoked(monkeypatch):
    actor = uuid.uuid4()
    membership = SimpleNamespace(role=MembershipRole.MEMBER)
    db = SimpleNamespace(delete=AsyncMock(), commit=AsyncMock())
    monkeypatch.setattr(communities, "get_membership", AsyncMock(return_value=membership))
    from app.services import chat
    monkeypatch.setattr(chat, "revoke_space_member", AsyncMock(side_effect=HTTPException(status_code=503, detail="unavailable")))
    with pytest.raises(HTTPException):
        await communities.remove_member(db, SimpleNamespace(id=uuid.uuid4()), actor)
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()


def test_project_input_and_task_versions_have_bounded_validated_values():
    project = ProjectCreate(name="Build together", resource_id=uuid.uuid4(), goal="Create a reproducible prototype", skills_needed=["CAD", "CAD", " testing "])
    assert project.skills_needed == ["CAD", "testing"]
    with pytest.raises(ValidationError):
        TaskUpdate(version=0, status="done")
    with pytest.raises(ValidationError):
        TaskUpdate(version=1, status="paid")


async def test_existing_mfa_cannot_be_replaced_by_setup_with_only_a_session():
    from app.services import auth
    actor = user(mfa_enabled=True, mfa_secret="existing-factor", mfa_last_counter=123)
    db = SimpleNamespace(commit=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await auth.setup_mfa(db, actor)
    assert exc.value.status_code == 409
    assert actor.mfa_enabled and actor.mfa_secret == "existing-factor"
    assert actor.mfa_last_counter == 123
    db.commit.assert_not_awaited()


async def test_old_email_link_cannot_verify_a_replacement_address():
    from app.core.security import create_email_verify_token
    from app.services.auth import confirm_email_verification
    actor = user(email="new@example.invalid", email_verified=False)
    token = create_email_verify_token(str(actor.id), "old@example.invalid")
    db = SimpleNamespace(get=AsyncMock(return_value=actor), commit=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await confirm_email_verification(db, token)
    assert exc.value.status_code == 400
    assert not actor.email_verified
    db.commit.assert_not_awaited()


async def test_current_email_link_verifies_the_exact_address():
    from app.core.security import create_email_verify_token
    from app.services.auth import confirm_email_verification
    actor = user(email="member@example.invalid", email_verified=False)
    db = SimpleNamespace(get=AsyncMock(return_value=actor), commit=AsyncMock())
    await confirm_email_verification(db, create_email_verify_token(str(actor.id), actor.email))
    assert actor.email_verified
    db.commit.assert_awaited_once()


async def test_chat_link_requires_recent_authentication_without_financial_kyc(monkeypatch):
    from starlette.requests import Request
    from app.api.chat import require_chat_link_auth
    from app.core.security import create_step_up_token
    # Linking a new identity always needs re-auth, even if a deployment relaxes
    # the separate transaction step-up setting.
    monkeypatch.setattr(settings, "REQUIRE_STEP_UP_AUTH", False)
    actor = user(kyc_status=KYCStatus.PENDING)
    request = Request({"type": "http", "headers": []})
    with pytest.raises(HTTPException) as exc:
        await require_chat_link_auth(request, actor)
    assert exc.value.status_code == 401
    request = Request({"type": "http", "headers": [(b"x-step-up-token", create_step_up_token(str(actor.id)).encode())]})
    assert await require_chat_link_auth(request, actor) is actor


async def test_step_up_header_is_accepted_for_configured_browser_origin(client):
    response = await client.options("/api/v1/chat/identity", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type,x-step-up-token",
    })
    assert response.status_code == 200
    assert "x-step-up-token" in response.headers["access-control-allow-headers"].lower()


def test_new_public_surfaces_cannot_publish_actionable_harm_instructions():
    from app.services.safety import require_public_text
    require_public_text("We are comparing battery recycling methods", "Open materials lab")
    with pytest.raises(HTTPException) as exc:
        require_public_text("Step by step instructions for making a pipe bomb")
    assert exc.value.status_code == 422


def test_external_source_links_encode_queries_and_never_change_destination():
    from urllib.parse import urlsplit, parse_qs
    from app.api.open_discovery import source_links
    query = "battery & q=evil # fragment"
    links = source_links(query)
    assert urlsplit(links[0].url).hostname == "patents.google.com"
    assert parse_qs(urlsplit(links[0].url).query)["q"] == [query]
    assert urlsplit(links[1].url).hostname == "worldwide.espacenet.com"


@pytest.mark.parametrize("viewer_role,owns_space,expected", [("creator", True, 200), ("creator", False, 403), ("admin", False, 200)])
async def test_private_reference_request_authorization_and_public_response_redaction(client, monkeypatch, viewer_role, owns_space, expected):
    from app.main import app
    from app.core.security import get_current_user
    from app.db.session import get_db
    from app.db.models.community import Community
    from app.db.models.institution import SpacePrivateRecord
    from app.api import institutions as institution_api

    actor = user(role=UserRole(viewer_role), mfa_enabled=True)
    now = datetime.now(timezone.utc)
    space = SimpleNamespace(id=uuid.uuid4(), created_by=actor.id if owns_space else uuid.uuid4(),
        name="Request test institution", slug="request-test", description="Research community",
        topic="general", visibility=CommunityVisibility.PUBLIC, is_institution=True,
        website_url=None, verification_status="unverified", created_at=now, updated_at=now)
    private = SpacePrivateRecord(community_id=space.id, reference="SP-PRIVATE-REQUEST-TEST", request_note="private evidence")

    async def get(model, _id):
        return space if model is Community else private if model is SpacePrivateRecord else None

    db = SimpleNamespace(get=get, scalar=AsyncMock(return_value=None), commit=AsyncMock())
    async def override_db():
        yield db
    async def override_actor():
        return actor

    app.dependency_overrides[get_current_user] = override_actor
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(institution_api, "write_audit_log", AsyncMock())
    try:
        result = await client.get(f"/api/v1/spaces/{space.id}/private", headers={"Authorization": "Bearer test-fixture"})
        assert result.status_code == expected, result.text
        if expected == 200:
            assert result.json()["reference"] == private.reference
            assert result.headers["cache-control"] == "private, no-store"
        else:
            assert private.reference not in result.text
        public = await client.get(f"/api/v1/institutions/{space.id}")
        assert public.status_code == 200
        assert private.reference not in public.text and "private evidence" not in public.text
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
