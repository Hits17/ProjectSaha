"""Refresh/logout races: mocked branch coverage plus isolated-DB concurrency cases."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects import postgresql

from app.services import auth
from app.core.security import create_refresh_token_pair, hash_password
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User, UserRole
from app.db.session import AsyncSessionLocal


def result(value):
    return NS(scalar_one_or_none=lambda: value)


async def test_refresh_rechecks_revocation_after_waiting_for_family_lock():
    token = NS(family_id=uuid.uuid4())
    db = NS(execute=AsyncMock(side_effect=[result(token), None, result(None)]), add=Mock(), commit=AsyncMock())
    with pytest.raises(HTTPException) as error:
        await auth.refresh_access_token(db, "test-token")
    assert error.value.status_code == 401
    db.add.assert_not_called()
    assert 'pg_advisory_xact_lock' in str(db.execute.call_args_list[1].args[0])
    assert 'FOR UPDATE' in str(db.execute.call_args_list[2].args[0].compile(dialect=postgresql.dialect()))


async def test_replayed_refresh_revokes_the_entire_family_without_minting():
    token = NS(family_id=uuid.uuid4(), used_at=datetime.now(timezone.utc))
    db = NS(execute=AsyncMock(side_effect=[result(token), None, result(token), None]), add=Mock(), commit=AsyncMock())
    with pytest.raises(HTTPException) as error:
        await auth.refresh_access_token(db, "test-token")
    assert error.value.status_code == 401
    db.add.assert_not_called()
    deletion = db.execute.call_args_list[-1].args[0].compile(dialect=postgresql.dialect())
    assert str(deletion).startswith('DELETE FROM refresh_tokens')
    assert token.family_id in deletion.params.values()
    db.commit.assert_awaited_once()


async def test_logout_of_rotated_parent_revokes_its_children():
    token = NS(family_id=uuid.uuid4())
    db = NS(execute=AsyncMock(side_effect=[result(token), None, None]), commit=AsyncMock())
    await auth.logout_user(db, "old-parent-token")
    assert 'pg_advisory_xact_lock' in str(db.execute.call_args_list[1].args[0])
    deletion = db.execute.call_args_list[-1].args[0].compile(dialect=postgresql.dialect())
    assert token.family_id in deletion.params.values()
    db.commit.assert_awaited_once()


async def test_empty_logout_does_not_touch_database():
    db = NS(execute=AsyncMock())
    await auth.logout_user(db, None)
    db.execute.assert_not_called()


@pytest.fixture
async def rotation_session():
    async with AsyncSessionLocal() as db:
        assert await db.scalar(text('SELECT current_database()')) == 'saha_test'
        user = User(email=f'session-{uuid.uuid4().hex}@tests.invalid', full_name='Session test',
                    hashed_password=hash_password('isolated-session-password'), role=UserRole.CREATOR, is_active=True)
        db.add(user)
        await db.flush()
        raw, hashed = create_refresh_token_pair()
        family = uuid.uuid4()
        db.add(RefreshToken(user_id=user.id, token_hash=hashed, family_id=family,
                            expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        await db.commit()
        uid = user.id
    yield raw, family
    async with AsyncSessionLocal() as db:
        await db.execute(delete(RefreshToken).where(RefreshToken.user_id == uid))
        await db.execute(delete(User).where(User.id == uid))
        await db.commit()


async def rotate(raw):
    async with AsyncSessionLocal() as db:
        try:
            return await auth.refresh_access_token(db, raw)
        except HTTPException as error:
            await db.rollback()
            return error.status_code


@pytest.mark.requires_db
async def test_concurrent_refresh_has_one_winner_and_reuse_revokes_family(rotation_session):
    raw, family = rotation_session
    results = await asyncio.gather(rotate(raw), rotate(raw))
    assert sum(isinstance(value, dict) for value in results) == 1
    assert 401 in results
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(RefreshToken).where(RefreshToken.family_id == family)) == 0


@pytest.mark.requires_db
async def test_logout_racing_rotation_leaves_no_refresh_descendants(rotation_session):
    raw, family = rotation_session
    async def logout():
        async with AsyncSessionLocal() as db:
            await auth.logout_user(db, raw)
    await asyncio.gather(rotate(raw), logout())
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(RefreshToken).where(RefreshToken.family_id == family)) == 0
