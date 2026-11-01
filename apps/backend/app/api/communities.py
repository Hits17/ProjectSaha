import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.community import (
    CommunityCreate,
    CommunityResponse,
    CommunityUpdate,
    MemberInvite,
    MemberResponse,
    MessageCreate,
    MessageResponse,
)
from app.core.audit import write_audit_log
from app.core.security import get_current_user, require_collaborator
from app.db.models.community import Community, CommunityVisibility, MembershipRole
from app.db.models.user import User
from app.db.session import get_db
from app.services import communities as community_svc

router = APIRouter(prefix="/api/v1/communities", tags=["communities"])
logger = structlog.get_logger()


async def _to_response(
    db: AsyncSession, community: Community, user_id: uuid.UUID
) -> CommunityResponse:
    resp = CommunityResponse.model_validate(community)
    resp.member_count = await community_svc.member_count(db, community.id)
    membership = await community_svc.get_membership(db, community.id, user_id)
    resp.is_member = membership is not None
    resp.my_role = membership.role if membership else None
    return resp


async def _load_visible(
    db: AsyncSession, community_id: uuid.UUID, user: User
) -> Community:
    """Fetch a community the user is allowed to see (public, or one they belong to)."""
    community = await community_svc.get_community(db, community_id)
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found")
    if community.visibility == CommunityVisibility.PRIVATE:
        membership = await community_svc.get_membership(db, community.id, user.id)
        if not membership:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found")
    return community


@router.post("", response_model=CommunityResponse, status_code=status.HTTP_201_CREATED)
async def create_community(
    body: CommunityCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_collaborator),
):
    community = await community_svc.create_community(db, current_user.id, body.model_dump())
    background_tasks.add_task(
        write_audit_log,
        action="community.created",
        user_id=current_user.id,
        resource_type="community",
        resource_id=community.id,
        metadata={"name": community.name, "topic": community.topic, "visibility": community.visibility.value},
    )
    return await _to_response(db, community, current_user.id)


@router.get("/me", response_model=list[CommunityResponse])
async def my_communities(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    communities = await community_svc.get_user_communities(db, current_user.id)
    return [await _to_response(db, c, current_user.id) for c in communities]


@router.get("", response_model=list[CommunityResponse])
async def browse_communities(
    q: str | None = Query(default=None, max_length=200),
    topic: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    communities = await community_svc.browse_communities(
        db, q=q, topic=topic, limit=limit, offset=offset
    )
    return [await _to_response(db, c, current_user.id) for c in communities]


@router.get("/{community_id}", response_model=CommunityResponse)
async def get_community(
    community_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    community = await _load_visible(db, community_id, current_user)
    return await _to_response(db, community, current_user.id)


@router.patch("/{community_id}", response_model=CommunityResponse)
async def update_community(
    community_id: uuid.UUID,
    body: CommunityUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_collaborator),
):
    community = await community_svc.get_community(db, community_id)
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found")
    community_svc.require_owner(community, current_user.id)

    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    community = await community_svc.update_community(db, community, changes)

    background_tasks.add_task(
        write_audit_log,
        action="community.updated",
        user_id=current_user.id,
        resource_type="community",
        resource_id=community.id,
        metadata={"fields": sorted(changes.keys())},
    )
    return await _to_response(db, community, current_user.id)


@router.post("/{community_id}/join", response_model=CommunityResponse)
async def join_community(
    community_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_collaborator),
):
    community = await community_svc.get_community(db, community_id)
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found")
    await community_svc.join_community(db, community, current_user.id)
    background_tasks.add_task(
        write_audit_log,
        action="community.joined",
        user_id=current_user.id,
        resource_type="community",
        resource_id=community.id,
    )
    return await _to_response(db, community, current_user.id)


@router.post("/{community_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_community(
    community_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_collaborator),
):
    community = await community_svc.get_community(db, community_id)
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found")
    await community_svc.leave_community(db, community, current_user.id)
    background_tasks.add_task(
        write_audit_log,
        action="community.left",
        user_id=current_user.id,
        resource_type="community",
        resource_id=community.id,
    )


@router.get("/{community_id}/members", response_model=list[MemberResponse])
async def list_members(
    community_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    community = await _load_visible(db, community_id, current_user)
    rows = await community_svc.list_members(db, community.id)

    # Emails are roster-management data, not browsing data. Only the owner and
    # moderators — who can actually add and remove members — receive them.
    membership = await community_svc.get_membership(db, community.id, current_user.id)
    may_see_emails = membership is not None and membership.role in (
        MembershipRole.OWNER, MembershipRole.MODERATOR
    )
    return [
        MemberResponse(
            user_id=m.user_id,
            full_name=name,
            email=email if may_see_emails else None,
            role=m.role,
            joined_at=m.created_at,
        )
        for m, name, email in rows
    ]


@router.post("/{community_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    community_id: uuid.UUID,
    body: MemberInvite,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_collaborator),
):
    """Add an existing Saha member to the community by email (owner/moderator only).

    This is how private communities grow — outsiders cannot self-join one."""
    community = await community_svc.get_community(db, community_id)
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found")
    await community_svc.require_manager(db, community, current_user.id)

    membership, name, email = await community_svc.add_member_by_email(db, community, body.email)
    background_tasks.add_task(
        write_audit_log,
        action="community.member_added",
        user_id=current_user.id,
        resource_type="community",
        resource_id=community.id,
        metadata={"added_user_id": str(membership.user_id), "email": email},
    )
    return MemberResponse(
        user_id=membership.user_id, full_name=name, email=email,
        role=membership.role, joined_at=membership.created_at,
    )


@router.delete("/{community_id}/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    community_id: uuid.UUID,
    member_user_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_collaborator),
):
    """Remove a member (owner/moderator only). The owner cannot be removed; to
    leave a community yourself, use POST /leave."""
    community = await community_svc.get_community(db, community_id)
    if not community:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community not found")
    await community_svc.require_manager(db, community, current_user.id)
    if member_user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use Leave to remove yourself.")

    await community_svc.remove_member(db, community, member_user_id)
    background_tasks.add_task(
        write_audit_log,
        action="community.member_removed",
        user_id=current_user.id,
        resource_type="community",
        resource_id=community.id,
        metadata={"removed_user_id": str(member_user_id)},
    )


@router.get("/{community_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    community_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=200),
    before: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    community = await _load_visible(db, community_id, current_user)
    membership = await community_svc.get_membership(db, community.id, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Join this community to read its chat."
        )
    rows = await community_svc.get_messages(db, community.id, limit=limit, before=before)
    return [
        MessageResponse(
            id=msg.id,
            community_id=msg.community_id,
            sender_id=msg.sender_id,
            sender_name=name,
            content=msg.content,
            created_at=msg.created_at,
        )
        for msg, name in rows
    ]


@router.post("/{community_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def post_message(
    community_id: uuid.UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_collaborator),
):
    community = await _load_visible(db, community_id, current_user)
    msg, sender_name = await community_svc.post_message(
        db, community, current_user.id, body.content.strip()
    )
    return MessageResponse(
        id=msg.id,
        community_id=msg.community_id,
        sender_id=msg.sender_id,
        sender_name=sender_name,
        content=msg.content,
        created_at=msg.created_at,
    )
