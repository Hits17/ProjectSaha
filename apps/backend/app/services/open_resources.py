"""Open Innovation Library service: admin-curated (and member-submitted,
admin-approved) open-source patents and research papers members can build on
royalty-free. Curation/moderation is admin-only; browsing needs no special
role; declaring "I'm building this" requires a verified member."""

import uuid

from fastapi import HTTPException, status as http_status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.open_resource import OpenResourceCreate, OpenResourceUpdate
from app.db.models.open_resource import (
    OpenResource,
    OpenResourceBuild,
    OpenResourceStatus,
    OpenResourceType,
)
from app.db.models.user import User


async def create_resource(
    db: AsyncSession,
    body: OpenResourceCreate,
    user_id: uuid.UUID,
    status: OpenResourceStatus = OpenResourceStatus.APPROVED,
) -> OpenResource:
    """Admin adds (approved immediately) or member submits (pending review)."""
    resource = OpenResource(**body.model_dump(), added_by=user_id, status=status)
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return resource


async def update_resource(
    db: AsyncSession, resource_id: uuid.UUID, body: OpenResourceUpdate
) -> OpenResource | None:
    resource = await db.get(OpenResource, resource_id)
    if resource is None:
        return None
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(resource, field, value)
    await db.commit()
    await db.refresh(resource)
    return await _attach_build_info(db, [resource])


async def moderate_resource(
    db: AsyncSession, resource_id: uuid.UUID, approve: bool
) -> OpenResource | None:
    """Approve or reject a pending member submission (idempotent on re-review)."""
    resource = await db.get(OpenResource, resource_id)
    if resource is None:
        return None
    resource.status = OpenResourceStatus.APPROVED if approve else OpenResourceStatus.REJECTED
    await db.commit()
    await db.refresh(resource)
    return resource


async def get_resource(
    db: AsyncSession,
    resource_id: uuid.UUID,
    count_view: bool = False,
    user_id: uuid.UUID | None = None,
) -> OpenResource | None:
    resource = await db.get(OpenResource, resource_id)
    if resource is None or not resource.is_active or resource.status != OpenResourceStatus.APPROVED:
        return None
    if count_view:
        # Atomic increment; skip ORM state so concurrent views don't clobber.
        await db.execute(
            update(OpenResource)
            .where(OpenResource.id == resource_id)
            .values(view_count=OpenResource.view_count + 1)
        )
        await db.commit()
        await db.refresh(resource)
    await _attach_build_info(db, [resource], user_id)
    return resource


async def browse(
    db: AsyncSession,
    q: str | None = None,
    resource_type: OpenResourceType | None = None,
    category: str | None = None,
    tag: str | None = None,
    limit: int = 30,
    offset: int = 0,
    include_inactive: bool = False,
    status: OpenResourceStatus | None = OpenResourceStatus.APPROVED,
    user_id: uuid.UUID | None = None,
) -> list[OpenResource]:
    """Public browse defaults to approved+active; admin passes
    include_inactive=True and status=None (or a specific status) to see all."""
    stmt = select(OpenResource)
    if not include_inactive:
        stmt = stmt.where(OpenResource.is_active.is_(True))
    if status is not None:
        stmt = stmt.where(OpenResource.status == status)
    if resource_type:
        stmt = stmt.where(OpenResource.resource_type == resource_type)
    if category:
        stmt = stmt.where(OpenResource.category == category)
    if tag:
        stmt = stmt.where(OpenResource.tags.any(tag.strip().lower()))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                OpenResource.title.ilike(pattern),
                OpenResource.summary.ilike(pattern),
                OpenResource.authors.ilike(pattern),
                OpenResource.organization.ilike(pattern),
                OpenResource.identifier.ilike(pattern),
            )
        )
    stmt = stmt.order_by(OpenResource.created_at.desc()).limit(limit).offset(offset)
    rows = list((await db.execute(stmt)).scalars().all())
    await _attach_build_info(db, rows, user_id)
    return rows


# ── "I'm building this" declarations ─────────────────────────────────────────

async def _attach_build_info(
    db: AsyncSession, resources: list[OpenResource], user_id: uuid.UUID | None = None
) -> OpenResource | None:
    """Annotate ORM rows with build_count / is_building for the response model."""
    if not resources:
        return None
    ids = [r.id for r in resources]
    counts = dict(
        (await db.execute(
            select(OpenResourceBuild.resource_id, func.count())
            .where(OpenResourceBuild.resource_id.in_(ids))
            .group_by(OpenResourceBuild.resource_id)
        )).all()
    )
    mine: set[uuid.UUID] = set()
    if user_id:
        mine = set(
            (await db.execute(
                select(OpenResourceBuild.resource_id).where(
                    OpenResourceBuild.resource_id.in_(ids),
                    OpenResourceBuild.user_id == user_id,
                )
            )).scalars().all()
        )
    for r in resources:
        r.build_count = int(counts.get(r.id, 0))
        r.is_building = r.id in mine
    return resources[0]


async def declare_build(
    db: AsyncSession, resource_id: uuid.UUID, user_id: uuid.UUID, note: str | None
) -> int:
    """Idempotent declare; returns the resource's new build count."""
    resource = await db.get(OpenResource, resource_id)
    if resource is None or not resource.is_active or resource.status != OpenResourceStatus.APPROVED:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Resource not found")

    existing = (await db.execute(
        select(OpenResourceBuild).where(
            OpenResourceBuild.resource_id == resource_id,
            OpenResourceBuild.user_id == user_id,
        )
    )).scalar_one_or_none()
    if existing:
        if note is not None:
            existing.note = note
    else:
        db.add(OpenResourceBuild(resource_id=resource_id, user_id=user_id, note=note))
    await db.commit()
    return await build_count(db, resource_id)


async def remove_build(db: AsyncSession, resource_id: uuid.UUID, user_id: uuid.UUID) -> int:
    existing = (await db.execute(
        select(OpenResourceBuild).where(
            OpenResourceBuild.resource_id == resource_id,
            OpenResourceBuild.user_id == user_id,
        )
    )).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.commit()
    return await build_count(db, resource_id)


async def build_count(db: AsyncSession, resource_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(OpenResourceBuild).where(
        OpenResourceBuild.resource_id == resource_id
    )
    return int((await db.execute(stmt)).scalar() or 0)


async def list_builders(db: AsyncSession, resource_id: uuid.UUID) -> list[dict]:
    rows = (await db.execute(
        select(OpenResourceBuild, User.full_name)
        .join(User, User.id == OpenResourceBuild.user_id)
        .where(OpenResourceBuild.resource_id == resource_id)
        .order_by(OpenResourceBuild.created_at.desc())
        .limit(100)
    )).all()
    return [
        {
            "user_id": b.user_id,
            "full_name": name,
            "note": b.note,
            "created_at": b.created_at,
        }
        for b, name in rows
    ]


# ── Demand-gap cross-link (search suggestions) ───────────────────────────────

def clean_suggestion_terms(terms: list[str | None], max_terms: int = 6) -> list[str]:
    """Keep distinct, meaningfully long terms for the ILIKE suggestion query."""
    seen: list[str] = []
    for t in terms:
        t = (t or "").strip().lower()
        if len(t) >= 3 and t not in seen:
            seen.append(t)
        if len(seen) >= max_terms:
            break
    return seen


async def suggest_for_terms(
    db: AsyncSession, terms: list[str | None], limit: int = 3
) -> list[OpenResource]:
    """Open resources matching any search term — shown when listings are scarce
    so unmet demand routes into 'build it yourself from the open library'."""
    cleaned = clean_suggestion_terms(terms)
    if not cleaned:
        return []
    clauses = []
    for t in cleaned:
        pattern = f"%{t}%"
        clauses.extend([
            OpenResource.title.ilike(pattern),
            OpenResource.summary.ilike(pattern),
        ])
    stmt = (
        select(OpenResource)
        .where(
            OpenResource.is_active.is_(True),
            OpenResource.status == OpenResourceStatus.APPROVED,
            or_(*clauses),
        )
        .order_by(OpenResource.view_count.desc())
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    await _attach_build_info(db, rows)
    return rows


# ── Digest support ───────────────────────────────────────────────────────────

async def new_resource_counts_since(db: AsyncSession, since) -> dict[str | None, int]:
    """Approved, active resources added after `since`, grouped by category."""
    rows = (await db.execute(
        select(OpenResource.category, func.count())
        .where(
            OpenResource.is_active.is_(True),
            OpenResource.status == OpenResourceStatus.APPROVED,
            OpenResource.created_at > since,
        )
        .group_by(OpenResource.category)
    )).all()
    return {category: int(count) for category, count in rows}


async def count_active(db: AsyncSession) -> int:
    stmt = select(func.count()).select_from(OpenResource).where(
        OpenResource.is_active.is_(True),
        OpenResource.status == OpenResourceStatus.APPROVED,
    )
    return int((await db.execute(stmt)).scalar() or 0)
