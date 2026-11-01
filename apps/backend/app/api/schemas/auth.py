import re

from pydantic import BaseModel, Field, field_validator

from app.core.passwords import validate_password
from app.db.models.user import UserRole

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(v: str) -> str:
    v = v.lower().strip()
    if not _EMAIL_RE.match(v):
        raise ValueError("Invalid email address format")
    return v


# Roles a user may self-assign at sign-up. ADMIN and LEGAL are provisioned
# internally — accepting them here would be a privilege escalation.
_SELF_REGISTER_ROLES = {UserRole.CREATOR, UserRole.MANUFACTURER}


class RegisterRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str
    full_name: str = Field(max_length=255)
    role: UserRole = UserRole.CREATOR

    @field_validator("email")
    @classmethod
    def email_format(cls, v: str) -> str:
        return _validate_email(v)

    @field_validator("password")
    @classmethod
    def password_rules(cls, v: str) -> str:
        return validate_password(v)

    @field_validator("role")
    @classmethod
    def role_allowed(cls, v: UserRole) -> UserRole:
        if v not in _SELF_REGISTER_ROLES:
            raise ValueError("Role must be 'creator' or 'manufacturer'")
        return v

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Full name cannot be empty")
        return v.strip()


class LoginRequest(BaseModel):
    email: str
    password: str
    # Second factor — required only when the account has MFA enabled.
    mfa_code: str | None = None

    @field_validator("email")
    @classmethod
    def email_format(cls, v: str) -> str:
        return _validate_email(v)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    # Optional: the refresh token is normally carried in an httpOnly cookie.
    # Kept for non-browser clients that pass it explicitly.
    refresh_token: str | None = None


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


# --- MFA (TOTP) ---
class MFASetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class MFAVerifyRequest(BaseModel):
    code: str


class MFAStatusResponse(BaseModel):
    mfa_enabled: bool


# --- Step-up re-authentication ---
class StepUpRequest(BaseModel):
    password: str
    mfa_code: str | None = None


class StepUpResponse(BaseModel):
    step_up_token: str
    expires_in_seconds: int


# --- SSE handshake ---
class StreamTicketResponse(BaseModel):
    ticket: str
    expires_in_seconds: int


# --- Email verification ---
class EmailVerifyConfirm(BaseModel):
    token: str


class MessageResponse(BaseModel):
    message: str
