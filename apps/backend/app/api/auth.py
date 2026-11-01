from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import (
    EmailVerifyConfirm,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    MFASetupResponse,
    MFAStatusResponse,
    MFAVerifyRequest,
    RefreshRequest,
    RegisterRequest,
    StepUpRequest,
    StepUpResponse,
    StreamTicketResponse,
    TokenResponse,
)
from app.api.schemas.user import UserResponse
from app.core.audit import write_audit_log
from app.core.clientip import client_ip
from app.core.config import settings
from app.core.ratelimit import AUTH_LIMIT, REFRESH_LIMIT, WRITE_LIMIT, limiter
from app.core.security import STEP_UP_MAX_AGE, create_sse_ticket, get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.services import auth as auth_svc

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

REFRESH_COOKIE = "saha_refresh"

# Kept as a module-level alias so existing call sites read unchanged; resolution
# now goes through the trusted-proxy logic in app.core.clientip (SAHA-011).
_client_ip = client_ip


def _set_refresh_cookie(response: Response, raw_refresh: str) -> None:
    """Store the long-lived refresh token in an httpOnly, SameSite cookie so it
    is never readable by JavaScript (XSS can't exfiltrate it). SameSite blocks
    cross-site sending, which protects the cookie-authenticated /refresh from CSRF."""
    if not settings.COOKIE_AUTH_ENABLED:
        return
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_refresh,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/api/v1/auth",
        domain=settings.COOKIE_DOMAIN or None,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path="/api/v1/auth",
        domain=settings.COOKIE_DOMAIN or None,
    )


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit(AUTH_LIMIT)
async def register(
    body: RegisterRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    user = await auth_svc.register_user(db, body.email, body.password, body.full_name, body.role)
    background_tasks.add_task(
        write_audit_log,
        action="user.register",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    # Fire off the verification email (no-op-safe if SMTP is down).
    background_tasks.add_task(
        auth_svc.send_verification_email, user.id, user.email, user.full_name
    )
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(AUTH_LIMIT)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_svc.login_user(db, body.email, body.password, body.mfa_code)
    _set_refresh_cookie(response, tokens["refresh_token"])
    background_tasks.add_task(
        write_audit_log,
        action="user.login",
        ip_address=_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        metadata={"email": body.email},
    )
    return tokens


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(REFRESH_LIMIT)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    # Prefer the httpOnly cookie; fall back to an explicit body token for
    # non-browser clients.
    raw = request.cookies.get(REFRESH_COOKIE) or (body.refresh_token if body else None)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    tokens = await auth_svc.refresh_access_token(db, raw)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return tokens


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    body: LogoutRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw = request.cookies.get(REFRESH_COOKIE) or (body.refresh_token if body else None)
    await auth_svc.logout_user(db, raw)
    _clear_refresh_cookie(response)
    background_tasks.add_task(
        write_audit_log,
        action="user.logout",
        user_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )


# ── MFA (TOTP) ────────────────────────────────────────────────────────────────

@router.post("/mfa/setup", response_model=MFASetupResponse)
@limiter.limit(WRITE_LIMIT)
async def mfa_setup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    secret, uri = await auth_svc.setup_mfa(db, current_user)
    return MFASetupResponse(secret=secret, otpauth_uri=uri)


@router.post("/mfa/enable", response_model=MFAStatusResponse)
@limiter.limit(WRITE_LIMIT)
async def mfa_enable(
    body: MFAVerifyRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await auth_svc.enable_mfa(db, current_user, body.code)
    background_tasks.add_task(
        write_audit_log, action="user.mfa_enabled", user_id=current_user.id,
        resource_type="user", resource_id=current_user.id,
    )
    return MFAStatusResponse(mfa_enabled=True)


@router.post("/mfa/disable", response_model=MFAStatusResponse)
@limiter.limit(WRITE_LIMIT)
async def mfa_disable(
    body: MFAVerifyRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await auth_svc.disable_mfa(db, current_user, body.code)
    background_tasks.add_task(
        write_audit_log, action="user.mfa_disabled", user_id=current_user.id,
        resource_type="user", resource_id=current_user.id,
    )
    return MFAStatusResponse(mfa_enabled=False)


@router.get("/mfa/status", response_model=MFAStatusResponse)
async def mfa_status(current_user: User = Depends(get_current_user)):
    return MFAStatusResponse(mfa_enabled=current_user.mfa_enabled)


# ── Step-up re-authentication ────────────────────────────────────────────────

@router.post("/step-up", response_model=StepUpResponse)
@limiter.limit(AUTH_LIMIT)
async def step_up(
    body: StepUpRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mint a short-lived token proving the user just re-authenticated.

    Required by irreversible or high-value actions — escrow release, contract
    execution, confidential document egress. A stolen access token is not
    sufficient for those: the attacker would also need the password (and second
    factor, where enrolled). Present the returned token in `X-Step-Up-Token`."""
    token = await auth_svc.step_up(db, current_user, body.password, body.mfa_code)
    background_tasks.add_task(
        write_audit_log, action="user.step_up", user_id=current_user.id,
        resource_type="user", resource_id=current_user.id,
        ip_address=client_ip(request), user_agent=request.headers.get("User-Agent"),
    )
    return StepUpResponse(step_up_token=token, expires_in_seconds=int(STEP_UP_MAX_AGE.total_seconds()))


# ── Server-sent events handshake ─────────────────────────────────────────────

@router.post("/stream-ticket", response_model=StreamTicketResponse)
@limiter.limit(REFRESH_LIMIT)
async def stream_ticket(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Exchange the (header-borne) access token for a 60-second stream ticket.

    EventSource cannot set an Authorization header, so something has to travel
    in the URL. Previously that was the full 15-minute access token, which then
    landed in nginx access logs and browser history (security/AUDIT.md
    SAHA-017). This ticket is scoped to the notification stream and expires
    before a log reader could realistically use it."""
    return StreamTicketResponse(ticket=create_sse_ticket(str(current_user.id)), expires_in_seconds=60)


# ── Email verification ──────────────────────────────────────────────────────

@router.post("/verify-email/request", response_model=MessageResponse)
@limiter.limit(AUTH_LIMIT)
async def request_email_verification(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    if not current_user.email_verified:
        background_tasks.add_task(
            auth_svc.send_verification_email,
            current_user.id, current_user.email, current_user.full_name,
        )
    return MessageResponse(message="If your email is unverified, a verification link has been sent.")


@router.post("/verify-email/confirm", response_model=MessageResponse)
@limiter.limit(AUTH_LIMIT)
async def confirm_email(
    body: EmailVerifyConfirm,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    await auth_svc.confirm_email_verification(db, body.token)
    return MessageResponse(message="Email verified.")
