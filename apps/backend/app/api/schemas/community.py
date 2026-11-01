import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models.community import CommunityVisibility, MembershipRole

# email-validator rejects .local TLDs; mirror the project-wide custom regex.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Topics are themed around IP research & development domains.
COMMUNITY_TOPICS = {
    "biotech_pharma",
    "clean_energy",
    "materials_science",
    "software_ai",
    "hardware_electronics",
    "consumer_products",
    "agritech_food",
    "medical_devices",
    "industrial_manufacturing",
    "general",
}


class CommunityCreate(BaseModel):
    model_config = {"str_strip_whitespace": True}
    name: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    topic: str
    visibility: CommunityVisibility = CommunityVisibility.PUBLIC

    @field_validator("topic")
    @classmethod
    def _valid_topic(cls, v: str) -> str:
        if v not in COMMUNITY_TOPICS:
            raise ValueError(f"topic must be one of: {', '.join(sorted(COMMUNITY_TOPICS))}")
        return v


class CommunityUpdate(BaseModel):
    model_config = {"str_strip_whitespace": True}
    name: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    topic: str | None = None
    visibility: CommunityVisibility | None = None

    @field_validator("topic")
    @classmethod
    def _valid_topic(cls, v: str | None) -> str | None:
        if v is not None and v not in COMMUNITY_TOPICS:
            raise ValueError(f"topic must be one of: {', '.join(sorted(COMMUNITY_TOPICS))}")
        return v


class CommunityResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    topic: str
    visibility: CommunityVisibility
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    # Derived per request.
    member_count: int = 0
    is_member: bool = False
    my_role: MembershipRole | None = None
    is_institution: bool = False
    website_url: str | None = None
    verification_status: str = "unverified"
    model_config = {"from_attributes": True}


class MemberInvite(BaseModel):
    email: str = Field(min_length=3, max_length=255)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    full_name: str
    # Populated only for community owners and moderators — they need it to manage
    # the roster. Previously every member email was returned to any authenticated
    # user for any public community, which made the member directory effectively
    # public (security/AUDIT.md SAHA-016).
    email: str | None = None
    role: MembershipRole
    joined_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    id: uuid.UUID
    community_id: uuid.UUID
    sender_id: uuid.UUID
    sender_name: str
    content: str
    created_at: datetime
