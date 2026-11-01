import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.community import (
    Community,
    CommunityMembership,
    CommunityMessage,
    CommunityVisibility,
    MembershipRole,
)
from app.db.models.user import User

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    base = _SLUG_STRIP.sub("-", name.lower()).strip("-")
    return base or "community"


async def _unique_slug(db: AsyncSession, name: str) -> str:
    base = _slugify(name)[:120]
    slug = base
    while True:
        exists = await db.scalar(select(Community.id).where(Community.slug == slug))
        if not exists:
            return slug
        slug = f"{base}-{uuid.uuid4().hex[:6]}"


async def member_count(db: AsyncSession, community_id: uuid.UUID) -> int:
    return int(await db.scalar(
        select(func.count()).select_from(CommunityMembership)
        .where(CommunityMembership.community_id == community_id)
    ) or 0)


async def get_membership(
    db: AsyncSession, community_id: uuid.UUID, user_id: uuid.UUID
) -> CommunityMembership | None:
    return await db.scalar(
        select(CommunityMembership).where(
            CommunityMembership.community_id == community_id,
            CommunityMembership.user_id == user_id,
        )
    )


async def create_community(
    db: AsyncSession, creator_id: uuid.UUID, data: dict
) -> Community:
    if data.get("visibility", CommunityVisibility.PUBLIC) == CommunityVisibility.PUBLIC:
        from app.services.safety import require_public_text
        require_public_text(data.get("description") or "", data["name"])
    slug = await _unique_slug(db, data["name"])
    community = Community(created_by=creator_id, slug=slug, **data)
    db.add(community)
    await db.flush()  # assigns community.id before we add the owner membership

    from app.db.models.institution import SpacePrivateRecord
    from app.services.institutions import new_reference
    db.add(SpacePrivateRecord(community_id=community.id, reference=new_reference()))

    db.add(CommunityMembership(
        community_id=community.id, user_id=creator_id, role=MembershipRole.OWNER
    ))
    await db.commit()
    await db.refresh(community)

    from app.core import metrics
    metrics.communities_created_total.inc()

    return community


async def get_community(db: AsyncSession, community_id: uuid.UUID) -> Community | None:
    return await db.get(Community, community_id)


async def browse_communities(
    db: AsyncSession,
    *,
    q: str | None = None,
    topic: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> list[Community]:
    """Public communities, most members first."""
    stmt = select(Community).where(Community.visibility == CommunityVisibility.PUBLIC)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Community.name.ilike(pattern), Community.description.ilike(pattern)))
    if topic:
        stmt = stmt.where(Community.topic == topic)

    member_sq = (
        select(func.count())
        .select_from(CommunityMembership)
        .where(CommunityMembership.community_id == Community.id)
        .scalar_subquery()
    )
    stmt = stmt.order_by(member_sq.desc(), Community.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_user_communities(db: AsyncSession, user_id: uuid.UUID) -> list[Community]:
    result = await db.execute(
        select(Community)
        .join(CommunityMembership, CommunityMembership.community_id == Community.id)
        .where(CommunityMembership.user_id == user_id)
        .order_by(Community.created_at.desc())
    )
    return list(result.scalars().all())


async def update_community(db: AsyncSession, community: Community, changes: dict) -> Community:
    community = (await db.execute(
        select(Community).where(Community.id == community.id).with_for_update()
        .execution_options(populate_existing=True)
    )).scalar_one()
    if any(key in changes and changes[key] is None for key in ("name", "topic", "visibility")):
        raise HTTPException(status_code=422, detail="Name, topic and visibility cannot be null.")
    from app.db.models.project import OpenProject
    if changes.get("visibility") == CommunityVisibility.PUBLIC and await db.get(OpenProject, community.id):
        raise HTTPException(status_code=422, detail="Projects are invite-only and must remain private.")
    if changes.get("visibility", community.visibility) == CommunityVisibility.PUBLIC:
        from app.services.safety import require_public_text
        require_public_text(changes.get("description", community.description) or "", changes.get("name", community.name))
    if community.is_institution and changes.get("visibility") == CommunityVisibility.PRIVATE:
        raise HTTPException(status_code=422, detail="Institution pages must remain public. Use a private community for private collaboration.")
    if changes.get("visibility") == CommunityVisibility.PRIVATE and community.visibility != CommunityVisibility.PRIVATE:
        from app.db.models.social import Post, PostVisibility
        from sqlalchemy import update
        await db.execute(update(Post).where(Post.community_id == community.id).values(visibility=PostVisibility.COMMUNITY))
    if community.is_institution and any(
        key in changes and changes[key] != getattr(community, key)
        for key in ("name", "website_url")
    ):
        community.verification_status = "unverified"
    for field, value in changes.items():
        setattr(community, field, value)
    await db.commit()
    await db.refresh(community)
    return community


async def join_community(
    db: AsyncSession, community: Community, user_id: uuid.UUID
) -> CommunityMembership:
    existing = await get_membership(db, community.id, user_id)
    if existing:
        return existing
    from app.db.models.project import OpenProject
    if community.visibility == CommunityVisibility.PRIVATE or await db.get(OpenProject, community.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This community is private — ask an owner to add you.",
        )
    membership = CommunityMembership(
        community_id=community.id, user_id=user_id, role=MembershipRole.MEMBER
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


async def leave_community(db: AsyncSession, community: Community, user_id: uuid.UUID) -> None:
    membership = await get_membership(db, community.id, user_id)
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not a member")
    if membership.role == MembershipRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owners cannot leave their own community.",
        )
    from app.services.chat import revoke_space_member
    await revoke_space_member(db, community.id, user_id)
    await db.delete(membership)
    await db.commit()


async def require_manager(
    db: AsyncSession, community: Community, user_id: uuid.UUID
) -> CommunityMembership:
    """Owners and moderators may manage the roster (invite / remove)."""
    membership = await get_membership(db, community.id, user_id)
    if not membership or membership.role not in (MembershipRole.OWNER, MembershipRole.MODERATOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner or a moderator can manage members.",
        )
    return membership


async def add_member_by_email(
    db: AsyncSession, community: Community, email: str
) -> tuple[CommunityMembership, str, str]:
    """Invite an existing Saha member into the community by their email.

    Works for both public and private communities — it is the only way to grow a
    private group, since outsiders cannot self-join one.
    """
    target = await db.scalar(select(User).where(User.email == email.lower().strip()))
    if not target or not target.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Saha member is registered with that email address.",
        )
    existing = await get_membership(db, community.id, target.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{target.full_name} is already a member.",
        )
    membership = CommunityMembership(
        community_id=community.id, user_id=target.id, role=MembershipRole.MEMBER
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership, target.full_name, target.email


async def remove_member(
    db: AsyncSession, community: Community, target_user_id: uuid.UUID
) -> None:
    membership = await get_membership(db, community.id, target_user_id)
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a member of this community")
    if membership.role == MembershipRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The owner cannot be removed."
        )
    from app.services.chat import revoke_space_member
    await revoke_space_member(db, community.id, target_user_id)
    await db.delete(membership)
    await db.commit()


async def list_members(
    db: AsyncSession, community_id: uuid.UUID
) -> list[tuple[CommunityMembership, str, str]]:
    result = await db.execute(
        select(CommunityMembership, User.full_name, User.email)
        .join(User, User.id == CommunityMembership.user_id)
        .where(CommunityMembership.community_id == community_id)
        .order_by(CommunityMembership.created_at)
    )
    return [(row[0], row[1], row[2]) for row in result.all()]


async def post_message(db: AsyncSession, community: Community, sender_id: uuid.UUID, content: str):
    """Legacy plaintext writes are intentionally unavailable after E2EE cutover."""
    raise HTTPException(status_code=410, detail="Plaintext chat is retired. Open the end-to-end encrypted chat workspace.")


async def get_messages(db: AsyncSession, community_id: uuid.UUID, *, limit: int = 100, before: uuid.UUID | None = None):
    raise HTTPException(status_code=410, detail="Legacy chat was not end-to-end encrypted. Open the encrypted chat workspace; legacy records are retained separately.")


def require_owner(community: Community, user_id: uuid.UUID) -> None:
    if community.created_by != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can do that"
        )


async def count_communities(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(Community)) or 0)
