"""Offline behavioral regressions for the social/workspace release."""
import tempfile
import uuid
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from starlette.datastructures import Headers

from app.api.schemas.project import ProjectCreate, ReferenceCreate, ReferenceUpdate
from app.api import projects
from app.db.models.community import CommunityVisibility, MembershipRole
from app.db.models.social import ModerationStatus, PostVisibility
from app.db.models.user import UserRole
from app.services import social_media as media, communities


def actor(**kw):
    return NS(**{ "id": uuid.uuid4(), "role": UserRole.CREATOR, **kw })


def test_standalone_project_and_reference_validation():
    assert ProjectCreate(name="Research team", goal="Build a working prototype").resource_id is None
    value = ReferenceCreate(title="  Design notes  ", url="https://docs.google.com/document/d/example", platform="google_docs", file_type="document")
    assert value.title == "Design notes" and not value.pinned
    with pytest.raises(ValidationError):
        ReferenceUpdate(**value.model_dump(), version=0)


@pytest.mark.parametrize("url", ["javascript:alert(1)", "http://example.com/file", "https://user:pass@example.com/file", "https://localhost/file", "https://127.0.0.1/file", "https://192.168.1.1/file", "https://[::1]/file", "https://example.local/file", "https://example.com:invalid/file", "https://good.example\\@bad.example/file", "https://example.org/\nfile"])
def test_reference_rejects_unsafe_or_local_urls(url):
    with pytest.raises(ValidationError):
        ReferenceCreate(title="Reference", url=url)


async def test_private_project_cannot_be_loaded_by_outsider_even_if_old_space_was_public(monkeypatch):
    project_id = uuid.uuid4()
    db = NS(get=AsyncMock(side_effect=[NS(resource_id=None), NS(visibility=CommunityVisibility.PUBLIC)]))
    monkeypatch.setattr(communities, "get_membership", AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as exc:
        await projects.load(db, project_id, actor())
    assert exc.value.status_code == 404


async def test_only_reference_author_or_manager_can_edit_and_only_manager_can_pin(monkeypatch):
    user = actor(); space = NS(id=uuid.uuid4()); own = NS(created_by=user.id)
    membership = AsyncMock(return_value=NS(role=MembershipRole.MEMBER))
    monkeypatch.setattr(communities, "get_membership", membership)
    await projects.reference_permission(None, space, user, own)
    for reference, pin in [(own, True), (NS(created_by=uuid.uuid4()), False)]:
        with pytest.raises(HTTPException) as exc:
            await projects.reference_permission(None, space, user, reference, pin_changed=pin)
        assert exc.value.status_code == 403
    membership.return_value = NS(role=MembershipRole.MODERATOR)
    await projects.reference_permission(None, space, user, NS(created_by=uuid.uuid4()), pin_changed=True)


@pytest.mark.parametrize("data,kind", [(b"\xff\xd8\xffpayload", "image/jpeg"), (b"\x89PNG\r\n\x1a\npayload", "image/png"), (b"RIFF1234WEBPpayload", "image/webp"), (b"\x00\x00\x00\x20ftypisom1234payload", "video/mp4"), (b"\x1a\x45\xdf\xa3webmpayload", "video/webm")])
def test_supported_media_signatures(data, kind):
    assert media.detect_media(data, kind) == kind


@pytest.mark.parametrize("data,kind", [(b"<svg onload='evil()' />", "image/png"), (b"\xff\xd8\xffdata", "image/png"), (b"", "video/mp4"), (b"<html>", "text/html")])
def test_active_content_or_mime_mismatch_is_rejected(data, kind):
    with pytest.raises(HTTPException) as exc:
        media.detect_media(data, kind)
    assert exc.value.status_code == 415


async def test_media_read_is_bounded(monkeypatch):
    monkeypatch.setattr(media, "IMAGE_LIMIT", 20)
    stream = tempfile.SpooledTemporaryFile(max_size=2048)
    stream.write(b"\xff\xd8\xff" + b"x" * 1000)
    stream.seek(0)
    file = UploadFile(stream, headers=Headers({"content-type": "image/jpeg"}))
    with pytest.raises(HTTPException) as exc:
        await media.read_media(file)
    assert exc.value.status_code == 413 and file.file.tell() == 21


async def test_draft_media_is_owner_only():
    owner = actor(); draft = NS(post_id=None, owner_id=owner.id)
    await media.assert_media_access(None, draft, owner)
    for viewer in (None, actor()):
        with pytest.raises(HTTPException) as exc:
            await media.assert_media_access(None, draft, viewer)
        assert exc.value.status_code == 404


async def test_published_media_inherits_removed_membership_and_deleted_post_policy(monkeypatch):
    from app.services import posts
    post = NS(id=uuid.uuid4(), author_id=uuid.uuid4(), visibility=PostVisibility.COMMUNITY,
              community_id=uuid.uuid4(), moderation_status=ModerationStatus.PUBLISHED, deleted_at=None)
    db = NS(get=AsyncMock(return_value=post))
    monkeypatch.setattr(posts, "_member_community_ids", AsyncMock(return_value=[]))
    with pytest.raises(HTTPException) as exc:
        await media.assert_media_access(db, NS(post_id=post.id), actor())
    assert exc.value.status_code == 404
    post.deleted_at = object()
    with pytest.raises(HTTPException) as exc:
        await media.assert_media_access(db, NS(post_id=post.id), actor(id=post.author_id))
    assert exc.value.status_code == 404


async def test_attachment_ownership_and_single_use():
    user = actor(); media_id = uuid.uuid4()
    for row in [NS(id=media_id, owner_id=uuid.uuid4(), post_id=None), NS(id=media_id, owner_id=user.id, post_id=uuid.uuid4())]:
        result = NS(scalars=lambda: [row])
        db = NS(execute=AsyncMock(side_effect=[None, result]))
        with pytest.raises(HTTPException) as exc:
            await media.attach(db, user, NS(id=uuid.uuid4()), [media_id])
        assert exc.value.status_code == 403


async def test_canonical_mentions_ignore_forged_labels_and_bound_notifications():
    person = actor(full_name="Actual Name")
    db = NS(execute=AsyncMock(return_value=NS(scalars=lambda: [person])))
    assert await media.normalize_mentions(db, f"Hi @[Fake Admin]({person.id})") == f"Hi @[Actual Name]({person.id})"
    with pytest.raises(HTTPException) as exc:
        await media.normalize_mentions(db, " ".join(f"@[Someone]({uuid.uuid4()})" for _ in range(11)))
    assert exc.value.status_code == 422


async def test_reaction_checks_access_before_writing(monkeypatch):
    from app.services import posts
    monkeypatch.setattr(posts, "assert_can_view", AsyncMock(side_effect=HTTPException(404, "Not found")))
    db = NS(execute=AsyncMock(), commit=AsyncMock())
    with pytest.raises(HTTPException):
        await media.react(db, NS(id=uuid.uuid4()), actor(), "like")
    db.execute.assert_not_called()
    db.commit.assert_not_called()
