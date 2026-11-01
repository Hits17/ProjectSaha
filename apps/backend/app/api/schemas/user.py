import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.passwords import validate_password
from app.db.models.user import KYCStatus, UserRole


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    kyc_status: KYCStatus
    is_active: bool
    email_verified: bool = False
    mfa_enabled: bool = False
    has_avatar: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    """Self-service profile edits. Identity fields (name/email) are accepted
    here but the endpoint rejects them once KYC is verified — verified identity
    must stay what was verified."""

    full_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)

    @field_validator("full_name")
    @classmethod
    def _name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("Full name cannot be empty")
        return v

    @field_validator("email")
    @classmethod
    def _email_format(cls, v: str | None) -> str | None:
        if v is None:
            return None
        from app.api.schemas.auth import _validate_email

        return _validate_email(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _policy(cls, v: str) -> str:
        return validate_password(v)


class KYCInitiateResponse(BaseModel):
    inquiry_id: str
    session_token: str
    mock: bool
    message: str


class KYCCompleteResponse(BaseModel):
    kyc_status: KYCStatus
    message: str
