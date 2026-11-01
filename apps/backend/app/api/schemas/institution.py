import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlsplit

from app.api.schemas.community import CommunityCreate, CommunityResponse, CommunityUpdate


def https_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Use an https URL without credentials")
    return value


class InstitutionCreate(CommunityCreate):
    website_url: str | None = Field(default=None, max_length=1000)
    _website = field_validator("website_url")(https_url)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Institution name must contain at least three non-space characters")
        return value.strip()


class InstitutionUpdate(CommunityUpdate):
    website_url: str | None = Field(default=None, max_length=1000)
    _website = field_validator("website_url")(https_url)


class InstitutionResponse(CommunityResponse):
    """Never add reference, evidence or reviewer notes to this public model."""


class VerificationPolicy(BaseModel):
    institution_verification_enabled: bool


class VerificationRequest(BaseModel):
    note: str = Field(min_length=10, max_length=2000)
    evidence_url: str | None = Field(default=None, max_length=1000)
    _evidence = field_validator("evidence_url")(https_url)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value):
        if len(value.strip()) < 10:
            raise ValueError("Explain your request in at least ten non-space characters")
        return value.strip()


class VerificationReview(BaseModel):
    decision: Literal["verified", "rejected", "unverified"]
    reason: str = Field(min_length=10, max_length=2000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value):
        if len(value.strip()) < 10:
            raise ValueError("Give a meaningful review reason")
        return value.strip()


class SpacePrivateResponse(BaseModel):
    community_id: uuid.UUID
    reference: str
    request_note: str | None
    evidence_url: str | None
    review_note: str | None
    requested_at: datetime | None
    reviewed_at: datetime | None
    model_config = {"from_attributes": True}


class AdminSpaceResponse(BaseModel):
    space: InstitutionResponse
    private: SpacePrivateResponse
