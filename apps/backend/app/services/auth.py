import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token_pair,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User, UserRole

# Verified against this hash when the email doesn't exist, so login latency
# doesn't reveal whether an account exists (timing-based user enumeration).
_DUMMY_HASH = hash_password("saha-timing-equalizer")


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: str,
    role: UserRole = UserRole.CREATOR,
) -> User:
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=email.lower().strip(),
        hashed_password=hash_password(password),
        full_name=full_name.strip(),
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login_user(
    db: AsyncSession, email: str, password: str, mfa_code: str | None = None
) -> dict:
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    # Account lockout: a locked account is rejected before the password check so
    # a brute-force run can't keep probing. Lock state applies only to real
    # accounts; non-existent emails still hit the timing-equalizer path below,
    # so lockout doesn't create a user-enumeration oracle.
    if user and user.locked_until and user.locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked due to repeated failed logins. Try again later.",
        )

    password_ok = verify_password(password, user.hashed_password if user else _DUMMY_HASH)
    if not user or not password_ok:
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
                user.failed_login_attempts = 0
            await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account deactivated")

    # Second factor. Only reached after the password verifies, so surfacing the
    # MFA requirement here is standard TOTP UX (not a credential oracle).
    if user.mfa_enabled and user.mfa_secret:
        if not mfa_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA code required"
            )
        if not await _consume_totp(db, user, mfa_code):
            # A wrong second factor counts toward lockout like a wrong password,
            # so a stolen-password attacker can't brute-force TOTP codes freely.
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
                user.failed_login_attempts = 0
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code"
            )

    # Successful auth clears any accumulated failure state.
    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None

    access_token = create_access_token(str(user.id), user.role.value)
    raw_refresh, hashed_refresh = create_refresh_token_pair()

    token = RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        family_id=uuid.uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(token)
    await db.commit()

    return {"access_token": access_token, "refresh_token": raw_refresh, "token_type": "bearer"}


async def _lock_refresh_family(db: AsyncSession, family_id: uuid.UUID) -> None:
    # Rotation and logout lock the family before touching individual token rows.
    # This also serializes an old-token logout against a newly rotated child.
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                     {"key": f"saha.auth.family:{family_id}"})


async def refresh_access_token(db: AsyncSession, raw_refresh_token: str) -> dict:
    token_hash = hash_token(raw_refresh_token)
    lookup = select(RefreshToken).where(RefreshToken.token_hash == token_hash,
                                       RefreshToken.expires_at > datetime.now(timezone.utc))
    stored = (await db.execute(lookup)).scalar_one_or_none()
    if stored is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    await _lock_refresh_family(db, stored.family_id)
    # A logout or another rotation may have completed while the lock was pending.
    stored = (await db.execute(lookup.where(RefreshToken.expires_at > datetime.now(timezone.utc)).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if stored is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    if stored.used_at is not None:
        await db.execute(delete(RefreshToken).where(RefreshToken.family_id == stored.family_id))
        await db.commit()
        raise HTTPException(status_code=401, detail="Token reuse detected. Please log in again.")

    user = await db.get(User, stored.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    stored.used_at = datetime.now(timezone.utc)
    access_token = create_access_token(str(user.id), user.role.value)
    raw_new, hashed_new = create_refresh_token_pair()
    db.add(RefreshToken(user_id=user.id, token_hash=hashed_new, family_id=stored.family_id,
                       expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)))
    await db.commit()
    return {"access_token": access_token, "refresh_token": raw_new, "token_type": "bearer"}


async def logout_user(db: AsyncSession, raw_refresh_token: str | None) -> None:
    if not raw_refresh_token:
        return
    stored = (await db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh_token)))).scalar_one_or_none()
    if stored is not None:
        await _lock_refresh_family(db, stored.family_id)
        await db.execute(delete(RefreshToken).where(RefreshToken.family_id == stored.family_id))
        await db.commit()


# ── Step-up re-authentication ────────────────────────────────────────────────

async def step_up(
    db: AsyncSession, user: User, password: str, mfa_code: str | None
) -> str:
    """Verify the user's credentials again and mint a step-up token.

    Guards irreversible actions (escrow release, contract execution, vault
    egress) so that possession of an access token alone is not enough to
    trigger them (security/AUDIT.md SAHA-015)."""
    from app.core.security import create_step_up_token

    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect"
        )
    if user.mfa_enabled and user.mfa_secret:
        if not mfa_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA code required"
            )
        if not await _consume_totp(db, user, mfa_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code"
            )
    return create_step_up_token(str(user.id))


# ── MFA (TOTP) ────────────────────────────────────────────────────────────────

async def _consume_totp(db: AsyncSession, user: User, code: str) -> bool:
    """Verify a TOTP code and burn its counter.

    A TOTP code is valid for its whole 30-second period plus the skew window, so
    without recording the accepted counter an intercepted code is replayable for
    up to 90 seconds (security/AUDIT.md SAHA-030). Recording it makes every code
    single-use.
    """
    from app.core import mfa as mfa_mod

    ok, counter = mfa_mod.verify_with_counter(
        mfa_mod.decrypt_secret(user.mfa_secret), code, last_counter=user.mfa_last_counter
    )
    if ok and counter is not None:
        user.mfa_last_counter = counter
        await db.commit()
    return ok


async def setup_mfa(db: AsyncSession, user: User) -> tuple[str, str]:
    """Generate + persist an (encrypted, not-yet-enabled) secret. Returns
    (secret, otpauth_uri) for the user to add to their authenticator app."""
    from app.core import mfa as mfa_mod

    if user.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is already enabled. Disable it using your existing authenticator before enrolling a replacement.")

    secret = mfa_mod.generate_secret()
    user.mfa_secret = mfa_mod.encrypt_secret(secret)
    user.mfa_enabled = False  # not active until the user confirms a code
    user.mfa_last_counter = None
    await db.commit()
    return secret, mfa_mod.provisioning_uri(secret, user.email)


async def enable_mfa(db: AsyncSession, user: User, code: str) -> None:
    if not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start MFA setup first")
    if not await _consume_totp(db, user, code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MFA code")
    user.mfa_enabled = True
    await db.commit()


async def disable_mfa(db: AsyncSession, user: User, code: str) -> None:
    if not user.mfa_enabled or not user.mfa_secret:
        return
    if not await _consume_totp(db, user, code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MFA code")
    user.mfa_enabled = False
    user.mfa_secret = None
    await db.commit()


# ── Email verification ──────────────────────────────────────────────────────

async def send_verification_email(user_id: uuid.UUID, email: str, full_name: str) -> None:
    """Compose + send the verification email. Safe to call as a BackgroundTask;
    swallows SMTP errors so a mail outage never fails the request."""
    from app.core.security import create_email_verify_token
    from app.integrations.email import send_email

    token = create_email_verify_token(str(user_id), email)
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    first = (full_name or "there").split(" ")[0]
    try:
        await send_email(
            to=email,
            subject="Verify your Saha account",
            html_body=(
                f"<p>Hi {first},</p>"
                f"<p>Confirm your email to activate your Saha account:</p>"
                f'<p><a href="{link}">Verify my email</a></p>'
                f"<p>This link expires in 24 hours.</p>"
            ),
            text_body=f"Hi {first},\nVerify your email: {link}\nThis link expires in 24 hours.",
        )
    except Exception:
        # Logged upstream; never break the request path on mail failure.
        pass


async def confirm_email_verification(db: AsyncSession, token: str) -> None:
    import hmac
    from app.core.security import decode_email_verify_token, email_binding

    claims = decode_email_verify_token(token)
    user = await db.get(User, uuid.UUID(claims["sub"]))
    if not user or not hmac.compare_digest(claims["email_binding"], email_binding(user.email)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification link")
    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
        await db.commit()
