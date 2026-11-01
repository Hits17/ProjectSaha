"""Notification service: create, query, mark-read, and an SSE-friendly poll.

Creation runs in its own session (like the audit logger) so it's safe to call
from a BackgroundTask and never entangles the request's main transaction.
"""

import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import Notification


async def notify_best_effort(user_id: uuid.UUID, type: str, title: str, body: str | None = None, link: str | None = None) -> None:
    """Keep a delivery outage from changing an already-committed domain result.

    Durable outbox retries are still a separate follow-up; only log identifiers,
    never message text or private reference/evidence data.
    """
    try:
        await notify(user_id, type, title, body, link)
    except Exception:
        import structlog
        structlog.get_logger().warning("notification_delivery_failed", user_id=str(user_id), event_type=type)


async def notify(
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> None:
    """Create a notification in a fresh session. BackgroundTask-safe."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        db.add(
            Notification(user_id=user_id, type=type, title=title, body=body, link=link)
        )
        await db.commit()


async def list_for_user(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 30, unread_only: bool = False
) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(min(limit, 100))
    return list((await db.execute(stmt)).scalars().all())


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(Notification).where(
        Notification.user_id == user_id, Notification.is_read.is_(False)
    )
    return int((await db.execute(stmt)).scalar() or 0)


async def mark_read(db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID) -> None:
    # Scoped to the owner — a user can only mark their own notifications read.
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(is_read=True)
    )
    await db.commit()


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()


async def fetch_since(
    db: AsyncSession, user_id: uuid.UUID, after: datetime, after_id: uuid.UUID | None = None
) -> list[Notification]:
    """Stable timestamp/id cursor: equal-timestamp batches cannot drop events."""
    from app.db.models.user import User
    cursor = Notification.created_at > after
    if after_id is not None:
        cursor = or_(cursor, and_(Notification.created_at == after, Notification.id > after_id))
    stmt = (
        select(Notification)
        .join(User, User.id == Notification.user_id)
        .where(Notification.user_id == user_id, User.is_active.is_(True), cursor)
        .order_by(Notification.created_at.asc(), Notification.id.asc())
        .limit(50)
    )
    return list((await db.execute(stmt)).scalars().all())
