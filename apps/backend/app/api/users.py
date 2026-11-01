import uuid

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, Response,
    UploadFile, status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.user import (
    ChangePasswordRequest,
    KYCCompleteResponse,
    KYCInitiateResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.core.audit import write_audit_log
from app.core.clientip import client_ip
from app.core.ratelimit import AUTH_LIMIT, KYC_LIMIT, WRITE_LIMIT, limiter
from app.core.security import get_current_user, hash_token
from app.db.models.user import KYCStatus, User
from app.db.session import get_db
from app.integrations.kyc import initiate_kyc_inquiry, simulate_mock_completion
from app.core.config import settings
from app.services import profile as profile_svc

router = APIRouter(prefix="/api/v1/users", tags=["users"])

REFRESH_COOKIE = "saha_refresh"  # keep in sync with app.api.auth


# Resolution goes through the trusted-proxy logic in app.core.clientip, so a
# client-supplied X-Forwarded-For can no longer forge the audited address
# (security/AUDIT.md SAHA-011).
_client_ip = client_ip


@router.get("/me", response_model=UserResponse)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
@limiter.limit(WRITE_LIMIT)
async def update_profile(
    body: UpdateProfileRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit name/email — allowed only until KYC verifies the identity."""
    if body.full_name is None and body.email is None:
        return current_user

    email_changed = await profile_svc.update_identity(db, current_user, body.full_name, body.email)
    if email_changed:
        from app.services.auth import send_verification_email

        background_tasks.add_task(
            send_verification_email, current_user.id, current_user.email, current_user.full_name
        )
    background_tasks.add_task(
        write_audit_log, action="user.profile_updated", user_id=current_user.id,
        resource_type="user", resource_id=current_user.id,
        ip_address=_client_ip(request),
        metadata={"email_changed": email_changed, "name_changed": body.full_name is not None},
    )
    return current_user


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(AUTH_LIMIT)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rotate the password. Every other session's refresh token is revoked;
    the session performing the change (identified by its refresh cookie) stays."""
    raw_cookie = request.cookies.get(REFRESH_COOKIE)
    await profile_svc.change_password(
        db, current_user, body.current_password, body.new_password,
        keep_token_hash=hash_token(raw_cookie) if raw_cookie else None,
    )
    background_tasks.add_task(
        write_audit_log, action="user.password_changed", user_id=current_user.id,
        resource_type="user", resource_id=current_user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )


# ── Profile picture ──────────────────────────────────────────────────────────

@router.post("/me/avatar", response_model=UserResponse)
@limiter.limit(WRITE_LIMIT)
async def upload_avatar(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await file.read()
    await profile_svc.set_avatar(db, current_user, data, file.content_type or "")
    background_tasks.add_task(
        write_audit_log, action="user.avatar_updated", user_id=current_user.id,
        resource_type="user", resource_id=current_user.id,
        metadata={"size_bytes": len(data)},
    )
    return current_user


@router.get("/me/avatar")
async def get_my_avatar(current_user: User = Depends(get_current_user)):
    data, content_type = await profile_svc.get_avatar(current_user)
    return Response(content=data, media_type=content_type,
                    headers={"Cache-Control": "private, no-cache"})


@router.get("/{user_id}/avatar")
async def get_user_avatar(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Any logged-in member may view another member's profile picture (shown
    beside reviews, community messages, and deal counterparties)."""
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    data, content_type = await profile_svc.get_avatar(user)
    return Response(content=data, media_type=content_type,
                    headers={"Cache-Control": "private, no-cache"})


@router.post("/me/kyc/initiate", response_model=KYCInitiateResponse)
@limiter.limit(KYC_LIMIT)
async def initiate_kyc(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.kyc_status == KYCStatus.VERIFIED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already verified")

    result = await initiate_kyc_inquiry(current_user.email)

    current_user.kyc_status = KYCStatus.IN_REVIEW
    current_user.kyc_inquiry_id = result["inquiry_id"]
    await db.commit()
    await db.refresh(current_user)

    background_tasks.add_task(
        write_audit_log,
        action="user.kyc_initiated",
        user_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        ip_address=_client_ip(request),
        metadata={"inquiry_id": result["inquiry_id"], "mock": result["mock"]},
    )

    return KYCInitiateResponse(
        inquiry_id=result["inquiry_id"],
        session_token=result["session_token"],
        mock=result["mock"],
        message="KYC initiated. In mock mode, call /me/kyc/complete to simulate approval." if result["mock"] else "Complete verification in the Persona widget.",
    )


@router.post("/me/kyc/complete", response_model=KYCCompleteResponse)
@limiter.limit(KYC_LIMIT)
async def complete_kyc_mock(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Development-only endpoint that simulates Persona approval.

    Gated on APP_ENV rather than on a standalone KYC_MOCK_MODE flag. The flag
    alone was true on the public deployment, which meant any anonymous
    registrant could self-approve to VERIFIED — the status that gates listing
    creation, proposals, transactions and vault download (security/AUDIT.md
    SAHA-004)."""
    if not settings.allows_mock_integrations:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if current_user.kyc_status == KYCStatus.VERIFIED:
        return KYCCompleteResponse(kyc_status=KYCStatus.VERIFIED, message="Already verified")

    if current_user.kyc_status != KYCStatus.IN_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Initiate KYC first via /me/kyc/initiate",
        )

    current_user.kyc_status = KYCStatus.VERIFIED
    await db.commit()
    await db.refresh(current_user)

    background_tasks.add_task(
        write_audit_log,
        action="user.kyc_verified",
        user_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        metadata={"mock": True},
    )

    return KYCCompleteResponse(kyc_status=KYCStatus.VERIFIED, message="KYC mock approval complete. User is now verified.")
