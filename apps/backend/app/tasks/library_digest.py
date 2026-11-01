"""Weekly Open Innovation Library digest.

An in-process loop (started from the app lifespan) wakes hourly and, when at
least LIBRARY_DIGEST_INTERVAL_DAYS have passed since the last digest AND new
approved resources exist in that window, notifies every active member in-app
and emails them (best-effort). Idempotency across restarts rides on the
notifications table itself: the newest 'library.digest' notification marks the
last run. Multi-worker safe: a Postgres advisory lock serializes concurrent
runs, and the last-run check inside the locked transaction makes the loser of
the race a no-op.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select, text

from app.core.config import settings
from app.db.models.notification import Notification
from app.db.models.user import User

logger = structlog.get_logger()

DIGEST_TYPE = "library.digest"
_CHECK_INTERVAL_SECONDS = 3600

_CATEGORY_LABELS = {
    "biotech_pharma": "Biotech & Pharma",
    "clean_energy": "Clean Energy",
    "materials_science": "Materials Science",
    "software_ai": "Software & AI",
    "hardware_electronics": "Hardware & Electronics",
    "consumer_products": "Consumer Products",
    "agritech_food": "AgriTech & Food",
    "medical_devices": "Medical Devices",
    "industrial_manufacturing": "Industrial Manufacturing",
    "general": "General",
}


def compose_digest(counts: dict[str | None, int]) -> tuple[str, str]:
    """(title, body) for a digest covering `counts` new resources by category."""
    total = sum(counts.values())
    noun = "resource" if total == 1 else "resources"
    title = f"{total} new open {noun} in the library this week"
    parts = sorted(counts.items(), key=lambda kv: -kv[1])
    body = ", ".join(
        f"{_CATEGORY_LABELS.get(cat or 'general', cat or 'General')} ({n})" for cat, n in parts
    )
    return title, f"New this week: {body}. Free to build on — take a look."


async def run_digest_once() -> bool:
    """Send the digest if one is due. Returns True when a digest was sent."""
    from app.db.session import AsyncSessionLocal
    from app.services import open_resources as resource_svc

    now = datetime.now(timezone.utc)
    interval = timedelta(days=settings.LIBRARY_DIGEST_INTERVAL_DAYS)

    async with AsyncSessionLocal() as db:
        # Serialize across API workers: only one process may run a digest pass at
        # a time (transaction-scoped advisory lock, released on commit/rollback).
        # The last-sent check below runs under the lock, so a losing worker sees
        # the winner's freshly written digest and bails.
        got_lock = (await db.execute(
            text("SELECT pg_try_advisory_xact_lock(hashtext('saha.library_digest'))")
        )).scalar()
        if not got_lock:
            return False

        last_sent = (await db.execute(
            select(func.max(Notification.created_at)).where(Notification.type == DIGEST_TYPE)
        )).scalar()
        if last_sent and now - last_sent < interval:
            return False

        window_start = last_sent or (now - interval)
        counts = await resource_svc.new_resource_counts_since(db, window_start)
        if not counts:
            return False

        title, body = compose_digest(counts)
        users = (await db.execute(
            select(User.id, User.email, User.full_name).where(User.is_active.is_(True))
        )).all()
        for user_id, _, _ in users:
            db.add(Notification(
                user_id=user_id, type=DIGEST_TYPE, title=title, body=body,
                link="/dashboard/library",
            ))
        await db.commit()

    # Email after the notifications are committed — a mail outage must never
    # roll back the in-app digest (which is also the idempotency marker).
    from app.integrations.email import send_email

    link = f"{settings.FRONTEND_URL}/dashboard/library"
    for _, email, full_name in users:
        first = (full_name or "there").split(" ")[0]
        try:
            await send_email(
                to=email,
                subject=title,
                html_body=(
                    f"<p>Hi {first},</p><p>{body}</p>"
                    f'<p><a href="{link}">Browse the Open Innovation Library</a></p>'
                ),
                text_body=f"Hi {first},\n{body}\nBrowse: {link}",
            )
        except Exception:
            # Best-effort: skip unreachable inboxes, keep going.
            continue

    logger.info("library_digest_sent", recipients=len(users), title=title)
    return True


async def digest_loop() -> None:
    """Hourly due-check loop; cancelled on app shutdown."""
    while True:
        try:
            await run_digest_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("library_digest_failed", error=str(e))
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
