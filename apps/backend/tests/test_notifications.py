"""Notifications: SSE auth gating and notification construction.

Kept DB-free (fake session + in-process ASGI) so it runs anywhere without a
migrated database or cross-event-loop connection-pool issues. The query helpers
(list/unread/mark) are thin SQLAlchemy statements exercised via the app.
"""

import uuid

import httpx
import pytest
from httpx import ASGITransport

from app.main import app
from app.services import notifications as notif


class _FakeSession:
    """Async-context session that records added objects; no real DB."""

    def __init__(self):
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass


async def test_notify_constructs_notification(monkeypatch):
    session = _FakeSession()
    import app.db.session as dbsession

    monkeypatch.setattr(dbsession, "AsyncSessionLocal", lambda: session)

    uid = uuid.uuid4()
    await notif.notify(uid, "proposal.submitted", "New offer", "body text", "/dashboard/proposals/x")

    assert len(session.added) == 1
    n = session.added[0]
    assert n.user_id == uid
    assert n.type == "proposal.submitted"
    assert n.title == "New offer"
    assert n.link == "/dashboard/proposals/x"


async def test_sse_requires_token():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # No ticket → FastAPI rejects the missing required query param (422).
        r = await c.get("/api/v1/notifications/stream")
        assert r.status_code == 422


async def test_sse_rejects_bad_ticket():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v1/notifications/stream", params={"ticket": "not-a-jwt"})
        assert r.status_code == 401


async def test_sse_rejects_an_access_token(auth_header):
    """An access token must NOT work here.

    The stream previously accepted the full access token as a query parameter,
    which put live credentials into nginx access logs and browser history
    (security/AUDIT.md SAHA-017). Only a short-lived, stream-scoped ticket is
    accepted now, so a token recovered from a log is useless against this route.
    """
    import uuid as _uuid
    token = auth_header(_uuid.uuid4())["Authorization"].removeprefix("Bearer ")
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v1/notifications/stream", params={"ticket": token})
        assert r.status_code == 401


async def test_notification_delivery_failure_does_not_fail_committed_action(monkeypatch):
    from unittest.mock import AsyncMock
    monkeypatch.setattr(notif, "notify", AsyncMock(side_effect=RuntimeError("test outage")))
    await notif.notify_best_effort(uuid.uuid4(), "institution.reviewed", "Status updated")


async def test_stream_cursor_cannot_reference_another_members_notification(client, monkeypatch):
    from types import SimpleNamespace
    from app.core.security import create_sse_ticket
    from app.db.models.user import User
    import app.db.session as dbsession

    owner_id = uuid.uuid4()
    actor = SimpleNamespace(id=owner_id, is_active=True)
    foreign = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def get(self, model, key): return actor if model is User else foreign
    monkeypatch.setattr(dbsession, "AsyncSessionLocal", Session)
    response = await client.get("/api/v1/notifications/stream", params={"ticket": create_sse_ticket(str(owner_id)), "after": str(foreign.id)})
    assert response.status_code == 400
    assert "body" not in response.json()
