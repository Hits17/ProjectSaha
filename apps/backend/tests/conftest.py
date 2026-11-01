"""
Shared test configuration and fixtures.

Before this file existed, every test was a unit test against a pure function and
**not one exercised a route end-to-end with authentication**. That is precisely
why two of the most serious findings in security/AUDIT.md survived a 141-test
suite: SAHA-003 (a response model leaking trade-secret fields to anonymous
callers) and SAHA-007 (a handler wired to the wrong authorization predicate) are
both invisible to unit tests and unmissable in an integration test.

`client` and the persona fixtures below give the regression suite a real ASGI
request path with real dependency resolution, so authorization and response
shape are asserted the way an attacker would probe them.

Tests that need a database are marked `requires_db` and skip when Postgres is
unreachable, so the suite still runs in a bare checkout.
"""

import asyncio
import os
import uuid

import pytest

# Test settings must be in place before app.core.config is imported anywhere.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-used-in-any-real-environment-0123456789")
os.environ.setdefault("VAULT_ENCRYPTION_KEY", "test-vault-key-v1-32-bytes-pad!!")
os.environ.setdefault("VAULT_ENCRYPTION_KEY_V2", "test-vault-key-v2-32-bytes-pad!!")
os.environ.setdefault("MINIO_ACCESS_KEY", "test-access-key")
os.environ.setdefault("MINIO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("REQUIRE_STEP_UP_AUTH", "false")
os.environ.setdefault("LIBRARY_DIGEST_ENABLED", "false")
# Isolate from whatever the local .env says about deployment. Without this the
# host allow-list rejects the test client's `Host: test` with a 400 before any
# route runs, and the suite silently stops testing what it thinks it tests.
os.environ.setdefault("ALLOWED_HOSTS", '["*"]')
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:3000"]')
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("KYC_MOCK_MODE", "true")
os.environ.setdefault("VAULT_V1_ROTATION_PENDING", "false")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def settings():
    from app.core.config import settings as s
    return s


# ── Database availability ────────────────────────────────────────────────────

def _db_reachable() -> bool:
    """Probe on a THROWAWAY engine.

    The shared `app.db.session.engine` binds its connection pool to whichever
    event loop first uses it. Probing with it here would bind it to this
    short-lived loop, and every later test would fail with "attached to a
    different loop" — an error that looks like a database problem and is not.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings
    from sqlalchemy.engine import make_url
    if make_url(settings.DATABASE_URL).database != "saha_test":
        return False

    async def _probe() -> bool:
        probe_engine = create_async_engine(settings.DATABASE_URL, poolclass=None, connect_args={"timeout": 5})
        try:
            async with probe_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await probe_engine.dispose()

    return asyncio.run(_probe())


@pytest.fixture(scope="session")
def db_available() -> bool:
    return _db_reachable()


@pytest.fixture(autouse=True)
def _skip_without_db(request):
    if request.node.get_closest_marker("requires_db") and not request.getfixturevalue("db_available"):
        pytest.skip("Postgres is not reachable — integration test skipped")


@pytest.fixture(autouse=True)
async def _engine_bound_to_this_loop(request):
    """Rebind the shared engine's pool to the running test's event loop.

    Each async test gets its own loop, while the engine is a module-level
    singleton that caches connections against the loop that created them.
    Disposing before and after keeps every DB test self-contained.
    """
    if not request.node.get_closest_marker("requires_db"):
        yield
        return

    from app.db.session import engine

    await engine.dispose()
    yield
    await engine.dispose()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "requires_db: integration test that needs a live Postgres"
    )


# ── HTTP client ──────────────────────────────────────────────────────────────

@pytest.fixture
async def client():
    """AsyncClient bound to the ASGI app, with lifespan skipped.

    Routes are exercised through the real dependency graph, so a missing or
    mis-wired `Depends` shows up here rather than in production.
    """
    import httpx
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Personas ─────────────────────────────────────────────────────────────────
#
# Tokens are minted directly rather than driven through /login: these fixtures
# exist to test *authorization*, and routing every test through the login flow
# would couple unrelated failures together.

def _token(user_id: uuid.UUID, role: str = "creator") -> str:
    from app.core.security import create_access_token
    return create_access_token(str(user_id), role)


@pytest.fixture
def auth_header():
    def _make(user_id: uuid.UUID, role: str = "creator") -> dict[str, str]:
        return {"Authorization": f"Bearer {_token(user_id, role)}"}
    return _make
