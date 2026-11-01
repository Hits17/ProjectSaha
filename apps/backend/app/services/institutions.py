import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.community import Community, CommunityVisibility
from app.db.models.institution import PlatformPolicy, SpacePrivateRecord
from app.db.models.user import User, UserRole
from app.services import communities


def new_reference() -> str:
    return f"SP-{uuid.uuid4().hex.upper()}"


async def verification_enabled(db: AsyncSession) -> bool:
    policy = await db.get(PlatformPolicy, 1)
    return bool(policy and policy.institution_verification_enabled)


async def set_verification_policy(db: AsyncSession, enabled: bool, actor: User) -> None:
    await db.execute(insert(PlatformPolicy).values(
        id=1, institution_verification_enabled=enabled, updated_by=actor.id,
    ).on_conflict_do_update(index_elements=[PlatformPolicy.id], set_={
        "institution_verification_enabled": enabled, "updated_by": actor.id,
        "updated_at": datetime.now(timezone.utc),
    }))
    await db.commit()


async def private_record(db: AsyncSession, community_id: uuid.UUID) -> SpacePrivateRecord:
    record = await db.get(SpacePrivateRecord, community_id)
    if record is None:
        # Repairs an older space lazily; only called behind private authorization.
        await db.execute(insert(SpacePrivateRecord).values(
            community_id=community_id, reference=new_reference(),
        ).on_conflict_do_nothing(index_elements=[SpacePrivateRecord.community_id]))
        record = await db.get(SpacePrivateRecord, community_id)
    return record


async def require_space_admin(db: AsyncSession, space: Community, user: User) -> None:
    if user.role == UserRole.ADMIN:
        # Platform administrators must still satisfy the existing MFA policy.
        from app.core.security import require_admin
        await require_admin(user)
    else:
        communities.require_owner(space, user.id)


async def create(db: AsyncSession, creator: User, data: dict) -> Community:
    from app.services.safety import require_public_text
    require_public_text(data.get("description") or "", data["name"])
    data["is_institution"] = True
    data["verification_status"] = "unverified"
    return await communities.create_community(db, creator.id, data)


async def get(db: AsyncSession, institution_id: uuid.UUID) -> Community:
    space = await db.get(Community, institution_id)
    if not space or not space.is_institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    return space


async def visible(db: AsyncSession, institution_id: uuid.UUID, viewer: User | None) -> Community:
    space = await get(db, institution_id)
    if space.visibility == CommunityVisibility.PRIVATE:
        if viewer is None or not await communities.get_membership(db, space.id, viewer.id):
            raise HTTPException(status_code=404, detail="Institution not found")
    return space


async def browse(db: AsyncSession, q: str | None, limit: int, offset: int) -> list[Community]:
    stmt = select(Community).where(Community.is_institution.is_(True), Community.visibility == CommunityVisibility.PUBLIC)
    if q:
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(or_(Community.name.ilike(pattern, escape="\\"), Community.description.ilike(pattern, escape="\\")))
    return list((await db.execute(stmt.order_by(Community.created_at.desc(), Community.id).limit(limit).offset(offset))).scalars().all())


async def update(db: AsyncSession, space: Community, changes: dict) -> Community:
    from app.services.safety import require_public_text
    require_public_text(changes.get("description", space.description) or "", changes.get("name", space.name))
    # A verified identity cannot change its name/domain while keeping the badge.
    identity_changed = any(key in changes and changes[key] != getattr(space, key) for key in ("name", "website_url"))
    if identity_changed:
        changes["verification_status"] = "unverified"
    return await communities.update_community(db, space, changes)


async def request_verification(db: AsyncSession, space: Community, note: str, evidence_url: str | None) -> SpacePrivateRecord:
    if not await verification_enabled(db):
        raise HTTPException(status_code=409, detail="Institution verification requests are not enabled.")
    space = (await db.execute(select(Community).where(Community.id == space.id).with_for_update().execution_options(populate_existing=True))).scalar_one()
    if space.verification_status == "pending":
        raise HTTPException(status_code=409, detail="This institution is already awaiting review.")
    if space.verification_status == "verified":
        raise HTTPException(status_code=409, detail="This institution is already verified.")
    record = await private_record(db, space.id)
    space.verification_status = "pending"
    record.request_note = note
    record.evidence_url = evidence_url
    record.requested_at = datetime.now(timezone.utc)
    record.review_note = None
    record.reviewed_at = None
    record.reviewed_by = None
    await db.commit()
    return record


async def review(db: AsyncSession, space: Community, decision: str, reason: str, actor: User) -> SpacePrivateRecord:
    # Lock and refresh so a simultaneous identity edit cannot inherit approval.
    space = (await db.execute(select(Community).where(Community.id == space.id).with_for_update().execution_options(populate_existing=True))).scalar_one()
    if decision in ("verified", "rejected") and space.verification_status != "pending":
        raise HTTPException(status_code=409, detail="Only pending requests can be approved or rejected.")
    if decision == "verified" and space.created_by == actor.id:
        raise HTTPException(status_code=403, detail="A different Saha administrator must verify your institution.")
    record = await private_record(db, space.id)
    space.verification_status = decision
    record.review_note = reason
    record.reviewed_by = actor.id
    record.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return record
