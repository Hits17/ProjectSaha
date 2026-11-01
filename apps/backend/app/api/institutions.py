import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.institution import (
    AdminSpaceResponse, InstitutionCreate, InstitutionResponse, InstitutionUpdate,
    SpacePrivateResponse, VerificationPolicy, VerificationRequest, VerificationReview,
)
from app.core.audit import write_audit_log
from app.core.ratelimit import ANON_READ_LIMIT, WRITE_LIMIT, limiter
from app.core.security import get_current_user, get_optional_user, require_admin, require_collaborator
from app.db.models.community import Community, CommunityVisibility
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.services import communities, institutions
from app.services.notifications import notify_best_effort

router = APIRouter(tags=["institutions"])


async def render(db: AsyncSession, space: Community, viewer: User | None) -> InstitutionResponse:
    result = InstitutionResponse.model_validate(space)
    result.member_count = await communities.member_count(db, space.id)
    if viewer:
        membership = await communities.get_membership(db, space.id, viewer.id)
        result.is_member = membership is not None
        result.my_role = membership.role if membership else None
    return result


def audit(tasks: BackgroundTasks, actor: User, action: str, space_id=None, **metadata):
    # Never place the private reference, request text or evidence URL in logs.
    tasks.add_task(write_audit_log, action=action, user_id=actor.id,
                   resource_type="community", resource_id=space_id, metadata=metadata)


@router.get("/api/v1/institutions/policy", response_model=VerificationPolicy)
@limiter.limit(ANON_READ_LIMIT)
async def public_policy(request: Request, db: AsyncSession = Depends(get_db)):
    return VerificationPolicy(institution_verification_enabled=await institutions.verification_enabled(db))


@router.get("/api/v1/institutions", response_model=list[InstitutionResponse])
@limiter.limit(ANON_READ_LIMIT)
async def browse(
    request: Request, q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=24, ge=1, le=100), offset: int = Query(default=0, ge=0, le=10000),
    db: AsyncSession = Depends(get_db), viewer: User | None = Depends(get_optional_user),
):
    return [await render(db, s, viewer) for s in await institutions.browse(db, q, limit, offset)]


@router.post("/api/v1/institutions", response_model=InstitutionResponse, status_code=201)
@limiter.limit(WRITE_LIMIT)
async def create(
    body: InstitutionCreate, request: Request, background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator),
):
    if body.visibility != CommunityVisibility.PUBLIC:
        raise HTTPException(status_code=422, detail="Institution pages are public. Create a private community for private collaboration.")
    space = await institutions.create(db, actor, body.model_dump())
    audit(background_tasks, actor, "institution.created", space.id)
    return await render(db, space, actor)


@router.get("/api/v1/institutions/{institution_id}", response_model=InstitutionResponse)
@limiter.limit(ANON_READ_LIMIT)
async def detail(
    institution_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
):
    return await render(db, await institutions.visible(db, institution_id, viewer), viewer)


@router.patch("/api/v1/institutions/{institution_id}", response_model=InstitutionResponse)
@limiter.limit(WRITE_LIMIT)
async def update(
    institution_id: uuid.UUID, body: InstitutionUpdate, request: Request, background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator),
):
    space = await institutions.get(db, institution_id)
    communities.require_owner(space, actor.id)
    if body.visibility not in (None, CommunityVisibility.PUBLIC):
        raise HTTPException(status_code=422, detail="Institution pages must remain public.")
    changes = body.model_dump(exclude_unset=True)
    if any(changes.get(key, "valid") is None for key in ("name", "topic", "visibility")):
        raise HTTPException(status_code=422, detail="Name, topic and visibility cannot be null.")
    space = await institutions.update(db, space, changes)
    audit(background_tasks, actor, "institution.updated", space.id, fields=sorted(changes))
    return await render(db, space, actor)


@router.get("/api/v1/spaces/{space_id}/private", response_model=SpacePrivateResponse)
async def private_details(
    space_id: uuid.UUID, background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user),
):
    space = await communities.get_community(db, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    await institutions.require_space_admin(db, space, actor)
    record = await institutions.private_record(db, space_id)
    await db.commit()
    audit(background_tasks, actor, "space.private_viewed", space.id)
    return record


@router.post("/api/v1/institutions/{institution_id}/verification", response_model=SpacePrivateResponse)
@limiter.limit(WRITE_LIMIT)
async def request_verification(
    institution_id: uuid.UUID, body: VerificationRequest, request: Request, background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_collaborator),
):
    space = await institutions.get(db, institution_id)
    communities.require_owner(space, actor.id)
    record = await institutions.request_verification(db, space, body.note.strip(), body.evidence_url)
    audit(background_tasks, actor, "institution.verification_requested", space.id)
    admins = (await db.execute(select(User.id).where(User.role == UserRole.ADMIN, User.is_active.is_(True)))).scalars().all()
    for admin_id in admins:
        background_tasks.add_task(notify_best_effort, admin_id, "institution.review_requested", "Institution verification requested",
                                  "An institution is awaiting review in the Institutions & Spaces admin queue.")
    return record


@router.put("/api/v1/admin/institutions/policy", response_model=VerificationPolicy)
async def set_policy(
    body: VerificationPolicy, background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_admin),
):
    await institutions.set_verification_policy(db, body.institution_verification_enabled, actor)
    audit(background_tasks, actor, "institution.verification_policy_changed", enabled=body.institution_verification_enabled)
    return body


@router.get("/api/v1/admin/spaces", response_model=list[AdminSpaceResponse])
async def admin_spaces(
    background_tasks: BackgroundTasks,
    verification_status: str | None = Query(default=None, pattern="^(unverified|pending|verified|rejected)$"),
    institutions_only: bool = False,
    limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0, le=10000),
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_admin),
):
    stmt = select(Community)
    if institutions_only:
        stmt = stmt.where(Community.is_institution.is_(True))
    if verification_status:
        stmt = stmt.where(Community.verification_status == verification_status)
    rows = list((await db.execute(stmt.order_by(Community.created_at.desc(), Community.id).limit(limit).offset(offset))).scalars().all())
    result = [AdminSpaceResponse(space=await render(db, space, actor), private=SpacePrivateResponse.model_validate(await institutions.private_record(db, space.id))) for space in rows]
    await db.commit()
    audit(background_tasks, actor, "space.private_directory_viewed", count=len(result))
    return result


@router.post("/api/v1/admin/institutions/{institution_id}/review", response_model=AdminSpaceResponse)
async def review(
    institution_id: uuid.UUID, body: VerificationReview, background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db), actor: User = Depends(require_admin),
):
    space = await institutions.get(db, institution_id)
    record = await institutions.review(db, space, body.decision, body.reason.strip(), actor)
    audit(background_tasks, actor, "institution.verification_reviewed", space.id, decision=body.decision)
    background_tasks.add_task(notify_best_effort, space.created_by, "institution.reviewed", "Institution verification updated",
                              f"Your institution's verification status is now {body.decision}. Open its page for details.", f"/institutions/{space.id}")
    return AdminSpaceResponse(space=await render(db, space, actor), private=SpacePrivateResponse.model_validate(record))
