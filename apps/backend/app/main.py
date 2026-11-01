import asyncio
import time
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.listings import router as listings_router
from app.api.materials import router as materials_router
from app.api.communities import router as communities_router
from app.api.proposals import router as proposals_router
from app.api.transactions import router as transactions_router
from app.api.settlement import router as settlement_router
from app.api.reviews import router as reviews_router
from app.api.demand import router as demand_router
from app.api.admin import router as admin_router
from app.api.search import router as search_router
from app.api.users import router as users_router
from app.api.notifications import router as notifications_router
from app.api.open_resources import router as open_resources_router
from app.api.social import router as social_router
from app.api.social_media import router as social_media_router
from app.api.institutions import router as institutions_router
from app.api.chat import router as chat_router
from app.api.open_discovery import router as open_discovery_router
from app.api.projects import router as projects_router
from app.api.research import router as research_router
from app.api.webhooks.kyc import router as kyc_webhook_router
from app.api.webhooks.stripe import router as stripe_webhook_router
from app.core import metrics  # noqa: F401 — registers Saha business metrics in the default Prometheus registry
from app.core.config import rotation_warnings, settings, validate_production_settings
from app.core.logging import configure_logging
from app.core.ratelimit import limiter
from app.core.release import source_fingerprint
from app.db.session import engine
from app.integrations import storage, vector

configure_logging()
logger = structlog.get_logger()
BACKEND_BUILD = "backend-" + source_fingerprint(Path(__file__).resolve().parents[1])[:20]


@asynccontextmanager
async def lifespan(app: FastAPI):
    problems = validate_production_settings(settings)
    if problems:
        for p in problems:
            logger.error("production_misconfiguration", problem=p)
        raise RuntimeError(
            "Refusing to start with insecure configuration: " + "; ".join(problems)
        )

    # Outstanding remediation is re-announced on every boot rather than logged
    # once and forgotten — a pending key rotation is not a state that should
    # quietly become permanent.
    for warning in rotation_warnings(settings):
        logger.warning("security_action_outstanding", detail=warning)

    logger.info("saha_startup", env=settings.APP_ENV.value, llm_provider=settings.LLM_PROVIDER)

    try:
        await storage.ensure_bucket_exists()
        logger.info("minio_bucket_ready", bucket=settings.MINIO_BUCKET)
    except Exception as e:
        logger.warning("minio_bucket_init_failed", error=str(e))

    try:
        await vector.ensure_collection_exists()
        logger.info("qdrant_collection_ready", collection=settings.QDRANT_COLLECTION)
    except Exception as e:
        logger.warning("qdrant_collection_init_failed", error=str(e))

    digest_task = None
    if settings.LIBRARY_DIGEST_ENABLED:
        from app.tasks.library_digest import digest_loop

        digest_task = asyncio.create_task(digest_loop())
        logger.info("library_digest_scheduler_started",
                    interval_days=settings.LIBRARY_DIGEST_INTERVAL_DAYS)

    yield

    if digest_task:
        digest_task.cancel()
        try:
            await digest_task
        except asyncio.CancelledError:
            pass

    logger.info("saha_shutdown")
    await engine.dispose()


app = FastAPI(
    title="Saha API",
    version="0.4.0",
    description="Transaction Operating System for Intellectual Property",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Rate limiter state. SlowAPIMiddleware enforces the limiter's default_limits on
# EVERY route (the anti-abuse backstop); per-route @limiter.limit decorators add
# stricter tiered ceilings on top.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


def _content_security_policy(path: str) -> str:
    """Strict CSP for the API. Swagger/ReDoc (dev-only) need CDN assets, so
    those paths get a scoped relaxation; every other response locks down to
    'none' since the API returns JSON, never HTML that loads sub-resources."""
    if path.startswith(("/docs", "/redoc")):
        return (
            "default-src 'none'; "
            "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "img-src 'self' data: https://cdn.jsdelivr.net; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
    return "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Request ID propagation + body-size guard + structured access log + security headers."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(
        request_id=request_id, method=request.method, path=request.url.path
    )

    # Body-size guard: fast-reject oversized declared payloads before parsing.
    # Multipart (vault uploads) gets the larger cap; everything else the JSON cap.
    content_length = request.headers.get("Content-Length")
    if content_length and content_length.isdigit():
        ctype = request.headers.get("Content-Type", "")
        is_multipart = ctype.startswith("multipart/form-data")
        cap = settings.MAX_UPLOAD_BYTES if is_multipart else settings.MAX_JSON_BODY_BYTES
        if int(content_length) > cap:
            structlog.contextvars.clear_contextvars()
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large", "request_id": request_id},
                headers={"X-Request-ID": request_id},
            )

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled_error", duration_ms=round((time.perf_counter() - start) * 1000, 1))
        structlog.contextvars.clear_contextvars()
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    if request.url.path not in ("/health/live", "/metrics/"):
        logger.info("request", status=response.status_code, duration_ms=duration_ms)
    structlog.contextvars.clear_contextvars()

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Saha-Build"] = BACKEND_BUILD
    if request.headers.get("Authorization") or request.url.path.startswith("/api/v1/auth"):
        response.headers["Cache-Control"] = "private, no-store"
        vary = {item.strip() for item in response.headers.get("Vary", "").split(",") if item.strip()}
        response.headers["Vary"] = ", ".join(sorted(vary | {"Authorization", "Origin"}))
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Content-Security-Policy", _content_security_policy(request.url.path))
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()"
    )
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    # Staging is on the same public host as production, so it gets HSTS too.
    if settings.is_internet_facing:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )
    return response


# Host allow-list (no-op in dev where ALLOWED_HOSTS=["*"])
if "*" not in settings.ALLOWED_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

app.add_middleware(GZipMiddleware, minimum_size=1024)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Step-Up-Token"],
    expose_headers=["X-Request-ID", "X-Step-Up-Required"],
)

# Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Routers
app.include_router(health_router, tags=["ops"])
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(kyc_webhook_router)
app.include_router(stripe_webhook_router)
app.include_router(listings_router)
app.include_router(materials_router)
app.include_router(communities_router)
app.include_router(proposals_router)
app.include_router(transactions_router)
app.include_router(settlement_router)
app.include_router(reviews_router)
app.include_router(demand_router)
app.include_router(admin_router)
app.include_router(search_router)
app.include_router(notifications_router)
app.include_router(open_resources_router)
app.include_router(social_router)
app.include_router(social_media_router)
app.include_router(institutions_router)
app.include_router(chat_router)
app.include_router(open_discovery_router)
app.include_router(projects_router)
app.include_router(research_router)
