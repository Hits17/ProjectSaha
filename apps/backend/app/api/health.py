"""
Health endpoints:
- GET /health/live  — liveness probe: process is up, no dependency checks.
- GET /health/ready — readiness probe: core dependencies (Postgres, Redis) only.
- GET /health       — deep check: every dependency and the active AI provider.
"""

import asyncio

import structlog
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from redis.asyncio import Redis

from app.core.config import settings
from app.core.security import require_admin
from app.db.session import engine
from app.integrations import storage, vector, email
from app.ai.client import llm

router = APIRouter()
logger = structlog.get_logger()


async def _check_postgres() -> str:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "healthy"
    except Exception as e:
        return f"unhealthy: {e}"


async def _check_redis() -> str:
    try:
        r = Redis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        return "healthy"
    except Exception as e:
        return f"unhealthy: {e}"


async def _check_minio() -> str:
    ok = await storage.ping()
    return "healthy" if ok else "unhealthy"


async def _check_qdrant() -> str:
    ok = await vector.ping()
    return "healthy" if ok else "unhealthy"


async def _check_smtp() -> str:
    ok = await email.ping()
    return "healthy" if ok else "unhealthy"


async def _check_ai() -> dict:
    """Never let provider exception text reach the caller.

    The deep check used to interpolate the raw exception into the response and
    was publicly reachable, so an anonymous request could read Python
    stack-trace fragments (security/AUDIT.md SAHA-019). Detail goes to the log,
    where operators can see it; the response carries a status only."""
    try:
        return await llm.ping()
    except Exception as e:  # noqa: BLE001
        logger.warning("ai_health_check_failed", provider=settings.LLM_PROVIDER, error=str(e))
        return {"active": settings.LLM_PROVIDER, "status": "unhealthy", "model": "unknown"}


@router.get("/health/live")
async def health_live():
    return {"status": "alive"}


@router.get("/health/ready")
async def health_ready(response: Response):
    postgres, redis = await asyncio.gather(_check_postgres(), _check_redis())
    ready = postgres == "healthy" and redis == "healthy"
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "postgres": postgres, "redis": redis}


@router.get("/health")
async def health(_: object = Depends(require_admin)):
    """Deep dependency check — ADMIN ONLY.

    This enumerates every backend component and its state, which is a map of the
    internal architecture. `/health/live` and `/health/ready` stay open for the
    reverse proxy and uptime monitoring; the detailed view does not."""
    postgres, redis, minio, qdrant, smtp, ai = await asyncio.gather(
        _check_postgres(),
        _check_redis(),
        _check_minio(),
        _check_qdrant(),
        _check_smtp(),
        _check_ai(),
    )

    checks = {
        "postgres": postgres,
        "redis": redis,
        "minio": minio,
        "qdrant": qdrant,
        "smtp": smtp,
        "ai_provider": ai,
    }

    all_healthy = all(
        v == "healthy" if isinstance(v, str) else v.get("status") == "healthy"
        for v in checks.values()
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
    }
