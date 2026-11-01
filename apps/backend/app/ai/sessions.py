"""
Redis-backed conversation state for multi-turn AI dialogues.
Each session is keyed by listing_id + user_id and expires after 24 hours.
"""

import json
import uuid

import redis.asyncio as aioredis

from app.core.config import settings

SESSION_TTL = 86400  # 24 hours

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _session_key(listing_id: uuid.UUID, user_id: uuid.UUID) -> str:
    return f"bom:session:{listing_id}:{user_id}"


async def get_messages(listing_id: uuid.UUID, user_id: uuid.UUID) -> list[dict]:
    r = get_redis()
    raw = await r.get(_session_key(listing_id, user_id))
    return json.loads(raw) if raw else []


async def append_message(listing_id: uuid.UUID, user_id: uuid.UUID, role: str, content: str) -> None:
    r = get_redis()
    key = _session_key(listing_id, user_id)
    messages = await get_messages(listing_id, user_id)
    messages.append({"role": role, "content": content})
    await r.setex(key, SESSION_TTL, json.dumps(messages))


async def set_messages(listing_id: uuid.UUID, user_id: uuid.UUID, messages: list[dict]) -> None:
    r = get_redis()
    await r.setex(_session_key(listing_id, user_id), SESSION_TTL, json.dumps(messages))


async def clear_session(listing_id: uuid.UUID, user_id: uuid.UUID) -> None:
    r = get_redis()
    await r.delete(_session_key(listing_id, user_id))
