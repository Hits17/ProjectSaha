"""Communities (social): input validation, owner policy, and slug generation."""

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.schemas.community import COMMUNITY_TOPICS, CommunityCreate, CommunityUpdate, MemberInvite
from app.db.models.community import CommunityVisibility
from app.services.communities import _slugify, require_owner


def _valid(**overrides):
    base = {
        "name": "Solid-state battery researchers",
        "description": "Sharing progress on solid electrolytes.",
        "topic": "clean_energy",
    }
    base.update(overrides)
    return base


def test_valid_community_create_defaults_public():
    c = CommunityCreate(**_valid())
    assert c.visibility == CommunityVisibility.PUBLIC


def test_unknown_topic_rejected():
    with pytest.raises(ValidationError):
        CommunityCreate(**_valid(topic="quantum_teleportation"))


def test_all_declared_topics_accepted():
    for topic in COMMUNITY_TOPICS:
        assert CommunityCreate(**_valid(topic=topic)).topic == topic


def test_short_name_rejected():
    with pytest.raises(ValidationError):
        CommunityCreate(**_valid(name="ab"))


def test_private_visibility_accepted():
    c = CommunityCreate(**_valid(visibility="private"))
    assert c.visibility == CommunityVisibility.PRIVATE


def test_update_is_partial():
    upd = CommunityUpdate(description="new blurb")
    assert upd.model_dump(exclude_unset=True) == {"description": "new blurb"}


def test_update_rejects_bad_topic():
    with pytest.raises(ValidationError):
        CommunityUpdate(topic="not-a-topic")


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Solid-State Battery R&D", "solid-state-battery-r-d"),
        ("  Clean Energy!!  ", "clean-energy"),
        ("AI/ML", "ai-ml"),
        ("???", "community"),
    ],
)
def test_slugify(name, expected):
    assert _slugify(name) == expected


def test_require_owner_allows_owner():
    owner = uuid.uuid4()
    community = SimpleNamespace(created_by=owner)
    require_owner(community, owner)  # must not raise


def test_require_owner_blocks_non_owner():
    community = SimpleNamespace(created_by=uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        require_owner(community, uuid.uuid4())
    assert exc.value.status_code == 403


def test_member_invite_normalizes_email():
    assert MemberInvite(email="  Person@Example.COM ").email == "person@example.com"


@pytest.mark.parametrize("bad", ["notanemail", "no@domain", "@x.com", "a@b"])
def test_member_invite_rejects_bad_email(bad):
    with pytest.raises(ValidationError):
        MemberInvite(email=bad)
