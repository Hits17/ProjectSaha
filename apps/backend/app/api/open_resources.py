"""Open Innovation Library — member-facing endpoints.

Reads are open to any logged-in member (same trust level as browsing public
communities): the library exists to be discovered, so no KYC gate. Writes that
put content or names in public view — submitting a resource for review and
declaring "I'm building this" — require a verified member, matching the
platform's reads=auth / writes=verified convention. Curation and moderation
live under /api/v1/admin/open-resources (admin-only, audited).
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.open_resource import (
    BuilderRow,
    BuildRequest,
    BuildStatusResponse,
    OpenResourceCreate,
    OpenResourceResponse,
)
from app.core.audit import write_audit_log
from app.core.ratelimit import WRITE_LIMIT, limiter
from app.core.security import get_current_user, require_collaborator
from app.db.models.open_resource import OpenResourceStatus, OpenResourceType
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.services import notifications as notif_svc
from app.services import open_resources as resource_svc

router = APIRouter(prefix="/api/v1/open-resources", tags=["open-resources"])


@router.get("", response_model=list[OpenResourceResponse])
async def browse_resources(
    q: str | None = Query(default=None, max_length=255),
    resource_type: OpenResourceType | None = None,
    category: str | None = Query(default=None, max_length=100),
    tag: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await resource_svc.browse(
        db, q=q, resource_type=resource_type, category=category, tag=tag,
        limit=limit, offset=offset, user_id=current_user.id,
    )


@router.post("/submissions", response_model=OpenResourceResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(WRITE_LIMIT)
async def submit_resource(
    body: OpenResourceCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_collaborator),
):
    """Member-suggested resource — enters the review queue as 'pending' and
    becomes publicly visible only once an admin approves it."""
    resource = await resource_svc.create_resource(
        db, body, current_user.id, status=OpenResourceStatus.PENDING
    )
    background_tasks.add_task(
        write_audit_log, action="open_resource.submitted", user_id=current_user.id,
        resource_type="open_resource", resource_id=resource.id,
        metadata={"title": resource.title},
    )
    # Ping the admins so the review queue doesn't sit unnoticed.
    admin_ids = (await db.execute(
        select(User.id).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
    )).scalars().all()
    for admin_id in admin_ids:
        background_tasks.add_task(
            notif_svc.notify, admin_id,
            "library.submission", "New library submission",
            f"“{resource.title}” was submitted to the Open Innovation Library and awaits review.",
            "/dashboard/library",
        )
    return resource


@router.get("/{resource_id}", response_model=OpenResourceResponse)
async def get_resource(
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = await resource_svc.get_resource(
        db, resource_id, count_view=True, user_id=current_user.id
    )
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return resource


# ── "I'm building this" ──────────────────────────────────────────────────────

@router.post("/{resource_id}/build", response_model=BuildStatusResponse)
@limiter.limit(WRITE_LIMIT)
async def declare_build(
    resource_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    body: BuildRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_collaborator),
):
    count = await resource_svc.declare_build(
        db, resource_id, current_user.id, body.note if body else None
    )
    background_tasks.add_task(
        write_audit_log, action="open_resource.build_declared", user_id=current_user.id,
        resource_type="open_resource", resource_id=resource_id,
    )
    return BuildStatusResponse(resource_id=resource_id, build_count=count, is_building=True)


@router.delete("/{resource_id}/build", response_model=BuildStatusResponse)
async def withdraw_build(
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_collaborator),
):
    count = await resource_svc.remove_build(db, resource_id, current_user.id)
    return BuildStatusResponse(resource_id=resource_id, build_count=count, is_building=False)


@router.get("/{resource_id}/builders", response_model=list[BuilderRow])
async def list_builders(
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await resource_svc.list_builders(db, resource_id)
