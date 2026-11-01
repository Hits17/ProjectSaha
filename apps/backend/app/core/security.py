import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.tokens import TokenError, decode_token, encode_token
from app.db.session import get_db

bearer_scheme = HTTPBearer()
_optional_bearer = HTTPBearer(auto_error=False)

# Token types. Kept as constants so a typo can't silently create a token class
# that no decoder ever checks.
ACCESS = "access"
EMAIL_VERIFY = "email_verify"
SSE_TICKET = "sse_ticket"
STEP_UP = "step_up"

# How recently the user must have re-authenticated to perform a high-value
# action (money movement, contract execution, confidential document egress).
STEP_UP_MAX_AGE = timedelta(minutes=10)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    if len(plain.encode()) > 72:
        return False
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, role: str) -> str:
    return encode_token(
        user_id, ACCESS,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        role=role,
    )


def create_refresh_token_pair() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash). Store only the hash."""
    raw = str(uuid.uuid4())
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_access_token(token: str) -> dict:
    try:
        return decode_token(token, expected_type=ACCESS)
    except TokenError:
        raise _unauthorized("Invalid or expired token")


def email_binding(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def create_email_verify_token(user_id: str, email: str) -> str:
    """Short-lived signed token emailed to the user to confirm their address."""
    return encode_token(user_id, EMAIL_VERIFY, timedelta(hours=24), email_binding=email_binding(email))


def decode_email_verify_token(token: str) -> dict:
    try:
        payload = decode_token(token, expected_type=EMAIL_VERIFY)
        uuid.UUID(payload["sub"])
        if not payload.get("email_binding"):
            raise TokenError("Email binding is required")
        return payload
    except (TokenError, KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link",
        )


def create_sse_ticket(user_id: str) -> str:
    """Single-purpose, 60-second token for the EventSource handshake.

    EventSource cannot send an Authorization header, so *something* has to ride
    in the URL. Previously that was the full access token, which then landed in
    nginx access logs and browser history (security/AUDIT.md SAHA-017). This
    ticket is minted by an authenticated POST, is valid only for the notification
    stream, and expires before a log reader could realistically use it."""
    return encode_token(user_id, SSE_TICKET, timedelta(seconds=60))


def decode_sse_ticket(token: str) -> str:
    try:
        return decode_token(token, expected_type=SSE_TICKET)["sub"]
    except (TokenError, KeyError):
        raise _unauthorized("Invalid or expired stream ticket")


def create_step_up_token(user_id: str) -> str:
    return encode_token(user_id, STEP_UP, STEP_UP_MAX_AGE)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    from app.db.models.user import User

    payload = decode_access_token(credentials.credentials)
    raw_id = payload.get("sub")
    try:
        user_id = uuid.UUID(raw_id)
    except (TypeError, ValueError):
        # A malformed `sub` should be a clean 401, not an unhandled 500.
        raise _unauthorized("Invalid token")

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise _unauthorized("User not found or inactive")
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: AsyncSession = Depends(get_db),
):
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


async def require_verified_user(user=Depends(get_current_user)):
    from app.db.models.user import KYCStatus

    if user.kyc_status != KYCStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="KYC verification required. Complete identity verification to proceed.",
        )
    return user


async def require_email_verified(user=Depends(get_current_user)):
    """Gate an endpoint on a verified email address — active only when
    REQUIRE_EMAIL_VERIFICATION is set, so it's a no-op until an operator opts in."""
    if settings.REQUIRE_EMAIL_VERIFICATION and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required. Check your inbox for the verification link.",
        )
    return user


async def require_collaborator(user=Depends(get_current_user)):
    """Open collaboration uses a confirmed email, not financial KYC.

    Transactional endpoints continue to use require_verified_user. Existing
    KYC-verified members retain access while confirming their email.
    """
    from app.db.models.user import KYCStatus

    if not user.email_verified and user.kyc_status != KYCStatus.VERIFIED:
        raise HTTPException(status_code=403, detail="Confirm your email to participate in open collaboration.")
    return user


async def require_admin(user=Depends(get_current_user)):
    """Administrator access, with MFA enforced.

    The admin console is the control plane — user roles, KYC override, dispute
    resolution, the revenue ledger. A single stolen password must not be enough
    (security/AUDIT.md SAHA-015), so an admin without a second factor is refused
    outright rather than merely warned. Enrolment is self-service via
    /api/v1/auth/mfa/setup, and the 403 says so."""
    from app.db.models.user import UserRole

    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    if settings.REQUIRE_ADMIN_MFA and not user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Multi-factor authentication is mandatory for administrators. "
                "Enrol at /api/v1/auth/mfa/setup, then sign in again."
            ),
        )
    return user


async def require_step_up(
    request: Request,
    user=Depends(require_verified_user),
):
    """Require a fresh re-authentication for irreversible or high-value actions.

    Applied to escrow release, contract execution and confidential document
    egress. The client obtains a step-up token from POST /api/v1/auth/step-up
    (password, plus TOTP when enrolled) and presents it in X-Step-Up-Token.
    A stolen access token alone is therefore not sufficient to move money or
    pull a counterparty's vault."""
    if not settings.REQUIRE_STEP_UP_AUTH:
        return user

    return validate_step_up_token(request, user)


def validate_step_up_token(request: Request, user):
    """Validate recent authentication independently of financial KYC policy."""
    token = request.headers.get("X-Step-Up-Token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This action requires re-authentication. Obtain a step-up token from /api/v1/auth/step-up.",
            headers={"X-Step-Up-Required": "1"},
        )
    try:
        payload = decode_token(token, expected_type=STEP_UP)
    except TokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Step-up token is invalid or has expired.",
            headers={"X-Step-Up-Required": "1"},
        )
    if payload.get("sub") != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Step-up token does not belong to the authenticated user.",
        )
    return user


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
