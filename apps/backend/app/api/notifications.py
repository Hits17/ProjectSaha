import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.notification import NotificationResponse, UnreadCountResponse
from app.core.security import decode_sse_ticket, get_current_user
from app.db.models.user import User
from app.db.models.notification import Notification
from app.db.session import get_db
from app.services import notifications as notif_svc

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await notif_svc.list_for_user(db, current_user.id, limit=limit, unread_only=unread_only)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return UnreadCountResponse(unread=await notif_svc.unread_count(db, current_user.id))


@router.post("/{notification_id}/read", status_code=204)
async def read_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await notif_svc.mark_read(db, current_user.id, notification_id)


@router.post("/read-all", status_code=204)
async def read_all(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await notif_svc.mark_all_read(db, current_user.id)


@router.get("/stream")
async def stream_notifications(request: Request, ticket: str = Query(...), after: uuid.UUID | None = Query(default=None)):
    """Server-Sent Events feed of new notifications.

    EventSource cannot send an Authorization header, so the handshake credential
    travels in the URL — and anything in a URL is written to the reverse proxy's
    access log and the browser's history. It therefore must not be the access
    token, which was the previous design (security/AUDIT.md SAHA-017).

    Instead the client POSTs to /api/v1/auth/stream-ticket with its bearer token
    and receives a 60-second, stream-scoped ticket. A ticket recovered from a log
    is useless: it expires almost immediately and grants nothing but this feed.

    The connection polls in a fresh DB session and auto-closes after a bounded
    lifetime so server-held connections recycle (the client reconnects, minting
    a fresh ticket each time)."""
    from app.db.session import AsyncSessionLocal
    try:
        user_id = uuid.UUID(decode_sse_ticket(ticket))
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid stream ticket") from None
    try:
        anchor_id = after or (uuid.UUID(request.headers["Last-Event-ID"]) if request.headers.get("Last-Event-ID") else None)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid notification cursor") from None
    initial_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    initial_id = uuid.UUID(int=0)
    async with AsyncSessionLocal() as db:
        actor = await db.get(User, user_id)
        if actor is None or not actor.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        if anchor_id:
            anchor = await db.get(Notification, anchor_id)
            if anchor is None or anchor.user_id != user_id:
                raise HTTPException(status_code=400, detail="Invalid notification cursor")
            initial_time, initial_id = anchor.created_at, anchor.id

    async def event_gen():
        from app.db.session import AsyncSessionLocal

        last_seen, last_id = initial_time, initial_id
        # ~30 min lifetime at a 3s poll cadence, then close for the client to reconnect.
        for _ in range(600):
            if await request.is_disconnected():
                break
            async with AsyncSessionLocal() as db:
                fresh = await notif_svc.fetch_since(db, user_id, last_seen, last_id)
            for n in fresh:
                last_seen, last_id = n.created_at, n.id
                data = {
                    "id": str(n.id),
                    "type": n.type,
                    "title": n.title,
                    "body": n.body,
                    "link": n.link,
                    "created_at": n.created_at.isoformat(),
                }
                yield f"id: {n.id}\ndata: {json.dumps(data)}\n\n"
            yield ": keep-alive\n\n"  # heartbeat
            await asyncio.sleep(3)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "private, no-store", "X-Accel-Buffering": "no"},
    )
