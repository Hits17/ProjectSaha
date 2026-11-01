"""Account-lockout policy (enterprise auth hardening, 2026-07-01):
repeated failed logins lock the account for a cooldown window, and a locked
account is rejected before the password check so brute-forcing can't continue.
Uses a lightweight fake AsyncSession so the logic is exercised without a live DB."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import hash_password
from app.db.models.user import User, UserRole
from app.services.auth import login_user


class _Result:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class _FakeSession:
    """Returns the same user for the initial SELECT; add/commit are no-ops."""

    def __init__(self, user):
        self._user = user

    async def execute(self, _stmt):
        return _Result(self._user)

    def add(self, _obj):
        pass

    async def commit(self):
        pass

    async def refresh(self, _obj):
        pass


def _user(**overrides) -> User:
    u = User(
        email="victim@example.com",
        hashed_password=hash_password("correct-horse-battery"),
        full_name="Victim",
        role=UserRole.CREATOR,
    )
    u.is_active = True
    u.failed_login_attempts = 0
    u.locked_until = None
    for k, v in overrides.items():
        setattr(u, k, v)
    return u


async def test_failed_logins_increment_and_lock():
    user = _user()
    db = _FakeSession(user)
    for _ in range(settings.LOGIN_MAX_ATTEMPTS):
        with pytest.raises(HTTPException) as exc:
            await login_user(db, user.email, "wrong-password")
        assert exc.value.status_code == 401
    # After hitting the threshold the account is locked and the counter resets.
    assert user.locked_until is not None
    assert user.locked_until > datetime.now(timezone.utc)
    assert user.failed_login_attempts == 0


async def test_locked_account_rejected_before_password_check():
    user = _user(locked_until=datetime.now(timezone.utc) + timedelta(minutes=10))
    db = _FakeSession(user)
    # Even the *correct* password is refused while locked, with 429.
    with pytest.raises(HTTPException) as exc:
        await login_user(db, user.email, "correct-horse-battery")
    assert exc.value.status_code == 429


async def test_successful_login_clears_failure_state():
    user = _user(failed_login_attempts=3)
    db = _FakeSession(user)
    tokens = await login_user(db, user.email, "correct-horse-battery")
    assert tokens["access_token"]
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


async def test_expired_lock_allows_login_again():
    user = _user(locked_until=datetime.now(timezone.utc) - timedelta(minutes=1))
    db = _FakeSession(user)
    tokens = await login_user(db, user.email, "correct-horse-battery")
    assert tokens["access_token"]
    assert user.locked_until is None
