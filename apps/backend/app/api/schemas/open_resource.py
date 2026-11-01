import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.community import COMMUNITY_TOPICS
from app.db.models.open_resource import OpenResourceStatus, OpenResourceType

# Curated license labels are discovery metadata, not a guarantee of patent
# permission. A publication/copyright license need not grant patent rights.
OPEN_LICENSES = {
    "public_domain",          # expired patent / dedicated to the public domain
    "cc0",
    "cc_by",
    "cc_by_sa",
    "mit",
    "apache_2_0",
    "gpl_3_0",
    "open_patent_pledge",     # patent kept in force but pledged royalty-free
    "defensive_publication",
}

_MAX_TAGS = 10


def _check_url(v: str) -> str:
    v = v.strip()
    if not v.startswith(("https://", "http://")):
        raise ValueError("source_url must be an http(s) URL")
    return v


def _check_license(v: str) -> str:
    if v not in OPEN_LICENSES:
        raise ValueError(f"license must be one of: {', '.join(sorted(OPEN_LICENSES))}")
    return v


def _check_category(v: str) -> str:
    if v not in COMMUNITY_TOPICS:
        raise ValueError(f"category must be one of: {', '.join(sorted(COMMUNITY_TOPICS))}")
    return v


def _check_tags(v: list[str]) -> list[str]:
    cleaned = [t.strip().lower() for t in v if t.strip()]
    if len(cleaned) > _MAX_TAGS:
        raise ValueError(f"At most {_MAX_TAGS} tags")
    if any(len(t) > 50 for t in cleaned):
        raise ValueError("Each tag must be 50 characters or fewer")
    return cleaned


class OpenResourceCreate(BaseModel):
    resource_type: OpenResourceType
    title: str = Field(min_length=5, max_length=300)
    summary: str | None = Field(default=None, max_length=10_000)
    authors: str | None = Field(default=None, max_length=500)
    organization: str | None = Field(default=None, max_length=255)
    identifier: str | None = Field(default=None, max_length=120)
    source_url: str = Field(min_length=10, max_length=1000)
    rights_evidence_url: str | None = Field(default=None, max_length=1000)
    rights_note: str | None = Field(default=None, max_length=3000)
    jurisdiction: str | None = Field(default=None, max_length=120)

    @field_validator("rights_evidence_url")
    @classmethod
    def _evidence_url(cls, v):
        from app.api.schemas.institution import https_url
        return https_url(v)
    license: str
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    published_year: int | None = Field(default=None, ge=1800, le=2100)

    @field_validator("source_url")
    @classmethod
    def _url(cls, v: str) -> str:
        return _check_url(v)

    @field_validator("license")
    @classmethod
    def _license(cls, v: str) -> str:
        return _check_license(v)

    @field_validator("category")
    @classmethod
    def _category(cls, v: str | None) -> str | None:
        return None if v is None else _check_category(v)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return _check_tags(v)


class OpenResourceUpdate(BaseModel):
    rights_evidence_url: str | None = Field(default=None, max_length=1000)
    rights_note: str | None = Field(default=None, max_length=3000)
    jurisdiction: str | None = Field(default=None, max_length=120)

    @field_validator("rights_evidence_url")
    @classmethod
    def _evidence_url(cls, v):
        from app.api.schemas.institution import https_url
        return https_url(v)
    resource_type: OpenResourceType | None = None
    title: str | None = Field(default=None, min_length=5, max_length=300)
    summary: str | None = Field(default=None, max_length=10_000)
    authors: str | None = Field(default=None, max_length=500)
    organization: str | None = Field(default=None, max_length=255)
    identifier: str | None = Field(default=None, max_length=120)
    source_url: str | None = Field(default=None, min_length=10, max_length=1000)
    license: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    published_year: int | None = Field(default=None, ge=1800, le=2100)
    is_active: bool | None = None

    @field_validator("source_url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        return None if v is None else _check_url(v)

    @field_validator("license")
    @classmethod
    def _license(cls, v: str | None) -> str | None:
        return None if v is None else _check_license(v)

    @field_validator("category")
    @classmethod
    def _category(cls, v: str | None) -> str | None:
        return None if v is None else _check_category(v)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _check_tags(v)


class OpenResourceResponse(BaseModel):
    rights_evidence_url: str | None = None
    rights_note: str | None = None
    jurisdiction: str | None = None
    id: uuid.UUID
    resource_type: OpenResourceType
    title: str
    summary: str | None
    authors: str | None
    organization: str | None
    identifier: str | None
    source_url: str
    license: str
    category: str | None
    tags: list[str]
    published_year: int | None
    status: OpenResourceStatus
    is_active: bool
    view_count: int
    # Social proof, attached by the service layer (not columns).
    build_count: int = 0
    is_building: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- "I'm building this" declarations ---

class BuildRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class BuildStatusResponse(BaseModel):
    resource_id: uuid.UUID
    build_count: int
    is_building: bool


class BuilderRow(BaseModel):
    user_id: uuid.UUID
    full_name: str
    note: str | None
    created_at: datetime


# --- Moderation (member submissions) ---

class RejectResourceRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
