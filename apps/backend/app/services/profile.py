"""Self-service profile: identity edits (locked after KYC), password change,
and profile pictures (stored plain in MinIO, served via the authenticated
avatar endpoint — unlike vault assets these are not encrypted)."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import KYCStatus, User
from app.integrations import storage

# Small, browser-native raster formats only — no SVG (script vector), no GIF.
ALLOWED_AVATAR_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2 MB


def ensure_identity_mutable(user: User) -> None:
    """Name/email are frozen once KYC verifies them — the marketplace trades on
    verified identity, so post-verification edits would defeat the check."""
    if user.kyc_status == KYCStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Name and email are locked after identity verification. Contact support to change them.",
        )


def validate_avatar(content_type: str | None, size: int) -> str:
    """Returns the file extension for a valid upload, else raises 400/413."""
    ext = ALLOWED_AVATAR_TYPES.get((content_type or "").split(";")[0].strip().lower())
    if not ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile picture must be a JPEG, PNG, or WebP image",
        )
    if size > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Profile picture must be {MAX_AVATAR_BYTES // (1024 * 1024)} MB or smaller",
        )
    if size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    return ext


async def update_identity(
    db: AsyncSession, user: User, full_name: str | None, email: str | None
) -> bool:
    """Apply pre-KYC name/email edits. Returns True when the email changed
    (caller re-sends the verification email)."""
    ensure_identity_mutable(user)

    email_changed = False
    if email is not None and email != user.email:
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        user.email = email
        # A new address is unverified by definition.
        user.email_verified = False
        user.email_verified_at = None
        email_changed = True

    if full_name is not None:
        user.full_name = full_name

    await db.commit()
    await db.refresh(user)
    return email_changed


async def change_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
    keep_token_hash: str | None,
) -> None:
    """Rotate the password and revoke every other session's refresh token —
    a password change is exactly when stolen sessions must die. The current
    session's token (from the httpOnly cookie) survives so the user isn't
    logged out of the browser they did this in."""
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    user.hashed_password = hash_password(new_password)

    stmt = select(RefreshToken).where(RefreshToken.user_id == user.id)
    if keep_token_hash:
        stmt = stmt.where(RefreshToken.token_hash != keep_token_hash)
    for token in (await db.execute(stmt)).scalars().all():
        await db.delete(token)

    await db.commit()


async def set_avatar(db: AsyncSession, user: User, data: bytes, content_type: str) -> None:
    ext = validate_avatar(content_type, len(data))
    old_key = user.avatar_key
    key = f"avatars/{user.id}/{uuid.uuid4()}.{ext}"
    await storage.upload_file(key, data, content_type)
    user.avatar_key = key
    await db.commit()
    if old_key:
        try:
            await storage.delete_file(old_key)
        except Exception:
            pass  # orphaned object; harmless


async def get_avatar(user: User) -> tuple[bytes, str]:
    """Returns (bytes, content_type) of the stored avatar, else 404."""
    if not user.avatar_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile picture")

    from app.integrations.storage import _s3_client
    from app.core.config import settings

    async with _s3_client() as s3:
        resp = await s3.get_object(Bucket=settings.MINIO_BUCKET, Key=user.avatar_key)
        async with resp["Body"] as stream:
            data = await stream.read()

    ext = user.avatar_key.rsplit(".", 1)[-1]
    content_type = {v: k for k, v in ALLOWED_AVATAR_TYPES.items()}.get(ext, "image/jpeg")
    return data, content_type
