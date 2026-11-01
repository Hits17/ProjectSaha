"""
Posts, comments and votes.

Authorization here follows the platform convention established in the security
audit: reads are gated on authentication, writes on verified KYC, and voting on
verified KYC too — because a vote is what produces reputation, and reputation
that a Sybil can mint is worse than no reputation at all.

Anti-gaming rules are enforced in this layer and mirrored by database
constraints where possible, on the principle from security/AUDIT.md SAHA-022:
a check that exists in exactly one place is a check waiting to be forgotten.
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.community import Community, CommunityMembership, CommunityVisibility
from app.db.models.social import (
    ContentReport, Follow, ModerationStatus, Post, PostComment, PostKind,
    PostVisibility, ReportReason, SavedPost, Vote, VoteTarget,
)
from app.db.models.user import User
from app.services import disclosure, safety, standing as standing_svc

logger = structlog.get_logger()

MAX_COMMENT_DEPTH = 1  # one level of threading — see the model docstring

# Only these appear in the feed. HELD, REJECTED and REMOVED are invisible to
# everyone except the author and admins.
VISIBLE_STATUSES = (ModerationStatus.PUBLISHED, ModerationStatus.FLAGGED,
                    ModerationStatus.APPROVED)

# Independent reports needed before a published post is pulled for review. One
# report is an opinion; several from unrelated members is a signal. Set above 1
# deliberately — a report button that auto-hides is a heckler's veto.
REPORTS_TO_HOLD = 3


# ── Visibility ───────────────────────────────────────────────────────────────

def _visibility_filter(viewer: User | None, member_community_ids: list[uuid.UUID]):
    """The set of posts a viewer may see.

    Mirrors the tiered-disclosure principle from SAHA-003: the filter is applied
    in the query, and the response model for anonymous callers carries only
    public-tier fields. Two layers, because one is how leaks happen.
    """
    if viewer is None:
        return (Post.visibility == PostVisibility.PUBLIC) & Post.moderation_status.in_(VISIBLE_STATUSES)

    # An author always sees their own posts, including held ones — otherwise a
    # held post looks like it silently vanished, which is worse than telling them.
    clauses = [
        (Post.visibility == PostVisibility.PUBLIC) & Post.moderation_status.in_(VISIBLE_STATUSES),
        (Post.visibility == PostVisibility.MEMBERS) & Post.moderation_status.in_(VISIBLE_STATUSES),
        Post.author_id == viewer.id,
    ]
    if member_community_ids:
        clauses.append(
            (Post.visibility == PostVisibility.COMMUNITY)
            & Post.community_id.in_(member_community_ids)
            & Post.moderation_status.in_(VISIBLE_STATUSES)
        )
    return or_(*clauses)


async def _member_community_ids(db: AsyncSession, user: User | None) -> list[uuid.UUID]:
    if user is None:
        return []
    return list((await db.execute(
        select(CommunityMembership.community_id).where(CommunityMembership.user_id == user.id)
    )).scalars().all())


async def assert_can_view(db: AsyncSession, post: Post, viewer: User | None) -> None:
    from app.db.models.user import UserRole

    if post.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # The author and admins can always reach a held post; nobody else can.
    if post.moderation_status not in VISIBLE_STATUSES:
        if viewer is not None and (viewer.id == post.author_id or viewer.role == UserRole.ADMIN):
            return
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post.visibility == PostVisibility.PUBLIC:
        return
    if viewer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.visibility == PostVisibility.MEMBERS or post.author_id == viewer.id:
        return
    if post.community_id and post.community_id in await _member_community_ids(db, viewer):
        return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")


# ── Posts ────────────────────────────────────────────────────────────────────

async def create_post(
    db: AsyncSession,
    author: User,
    *,
    body: str,
    title: str | None = None,
    kind: PostKind = PostKind.UPDATE,
    visibility: PostVisibility = PostVisibility.MEMBERS,
    community_id: uuid.UUID | None = None,
    link_url: str | None = None,
    listing_id: uuid.UUID | None = None,
    resource_id: uuid.UUID | None = None,
    acknowledged_disclosure: bool = False,
    media_ids: list[uuid.UUID] | None = None,
) -> Post:
    if visibility == PostVisibility.COMMUNITY or community_id is not None:
        if community_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="A community post needs a community")
        member = await db.scalar(
            select(CommunityMembership).where(
                CommunityMembership.community_id == community_id,
                CommunityMembership.user_id == author.id,
            )
        )
        if member is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Join this community to post in it")
        space = await db.get(Community, community_id)
        if space is None:
            raise HTTPException(status_code=404, detail="Space not found")
        if space.visibility == CommunityVisibility.PRIVATE and visibility != PostVisibility.COMMUNITY:
            raise HTTPException(status_code=422, detail="Posts in a private space must use community visibility.")

    # Attaching a listing asserts ownership of it. Without this a member could
    # attach someone else's listing to their own post and imply authorship.
    if listing_id is not None:
        from app.db.models.listing import IPListing

        listing = await db.get(IPListing, listing_id)
        if listing is None or listing.creator_id != author.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="You can only attach your own listings")

    from app.services.social_media import normalize_mentions
    body = await normalize_mentions(db, body)

    # ── Content safety ───────────────────────────────────────────────────────
    # Runs BEFORE the disclosure check: disclosure protects the author from
    # themselves and is dismissible; safety protects everyone else and is not.
    verdict = safety.escalate_for_visibility(
        safety.classify(body, title, visibility.value), visibility.value
    )
    if verdict.action is safety.SafetyAction.BLOCK:
        logger.warning(
            "post_blocked_by_safety", author_id=str(author.id),
            categories=verdict.categories, reason=verdict.reason,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "content_blocked",
                "message": verdict.author_message,
                "categories": verdict.categories,
            },
        )

    assessment = disclosure.analyse(body, title)
    flagged = assessment["risk"] != "none" and visibility == PostVisibility.PUBLIC

    # The composer surfaces the warning first; reaching here with a high-risk
    # public post and no acknowledgement means the client skipped that step.
    # Refuse rather than silently publish — the whole point is one deliberate
    # moment of friction before an irreversible disclosure.
    if flagged and assessment["risk"] == "high" and not acknowledged_disclosure:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "disclosure_warning",
                "message": disclosure.warning_for(assessment, visibility.value),
                "signals": assessment["signals"],
            },
        )

    moderation_status = {
        safety.SafetyAction.ALLOW: ModerationStatus.PUBLISHED,
        safety.SafetyAction.FLAG: ModerationStatus.FLAGGED,
        safety.SafetyAction.HOLD: ModerationStatus.HELD,
    }[verdict.action]

    post = Post(
        author_id=author.id,
        body=body.strip(),
        title=(title or None) and title.strip(),
        kind=kind,
        visibility=visibility,
        community_id=community_id,
        link_url=link_url,
        listing_id=listing_id,
        resource_id=resource_id,
        disclosure_flagged=flagged,
        moderation_status=moderation_status,
        safety_categories=verdict.categories,
        safety_reason=verdict.reason if verdict.categories else None,
        held_at=datetime.now(timezone.utc) if moderation_status is ModerationStatus.HELD else None,
    )
    db.add(post)
    await db.flush()
    from app.services.social_media import attach
    await attach(db, author, post, media_ids or [])
    post.hot_rank = standing_svc.hot_rank(0, datetime.now(timezone.utc))
    await db.commit()
    await db.refresh(post)

    from app.core import metrics
    if hasattr(metrics, "posts_created_total"):
        metrics.posts_created_total.inc()

    return post


async def get_post(db: AsyncSession, post_id: uuid.UUID) -> Post | None:
    return await db.scalar(select(Post).where(Post.id == post_id))


async def list_feed(
    db: AsyncSession,
    viewer: User | None,
    *,
    sort: str = "hot",
    kind: PostKind | None = None,
    community_id: uuid.UUID | None = None,
    author_id: uuid.UUID | None = None,
    following_only: bool = False,
    q: str = "",
    limit: int = 20,
    offset: int = 0,
) -> list[Post]:
    stmt = select(Post).where(
        Post.deleted_at.is_(None),
        _visibility_filter(viewer, await _member_community_ids(db, viewer)),
    )
    if q.strip():
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(or_(Post.body.ilike(f"%{term}%", escape="\\"), Post.title.ilike(f"%{term}%", escape="\\")))
    if kind is not None:
        stmt = stmt.where(Post.kind == kind)
    if community_id is not None:
        stmt = stmt.where(Post.community_id == community_id)
    if author_id is not None:
        stmt = stmt.where(Post.author_id == author_id)
    if following_only and viewer is not None:
        followees = select(Follow.followee_id).where(Follow.follower_id == viewer.id)
        stmt = stmt.where(Post.author_id.in_(followees))

    order = {
        "hot": Post.hot_rank.desc(),
        "new": Post.created_at.desc(),
        "top": Post.score.desc(),
    }.get(sort, Post.hot_rank.desc())

    stmt = stmt.order_by(order, Post.created_at.desc(), Post.id.desc()).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())


async def edit_post(db: AsyncSession, post: Post, author: User, body: str, title: str | None, *, acknowledged_disclosure: bool = False) -> Post:
    if post.author_id != author.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your post")
    await assert_can_view(db, post, author)
    if not body.strip():
        raise HTTPException(status_code=422, detail="Post body cannot be empty")
    from app.services.social_media import normalize_mentions
    body = await normalize_mentions(db, body)
    verdict = safety.escalate_for_visibility(safety.classify(body, title, post.visibility.value), post.visibility.value)
    if verdict.action is safety.SafetyAction.BLOCK:
        raise HTTPException(status_code=422, detail={"code": "content_blocked", "message": verdict.author_message, "categories": verdict.categories})
    assessment = disclosure.analyse(body, title)
    flagged = assessment["risk"] != "none" and post.visibility == PostVisibility.PUBLIC
    if flagged and assessment["risk"] == "high" and not acknowledged_disclosure:
        raise HTTPException(status_code=409, detail={"code": "disclosure_warning", "message": disclosure.warning_for(assessment, post.visibility.value), "signals": assessment["signals"]})
    # Held/rejected/removed content needs a human decision even after an edit.
    if post.moderation_status in VISIBLE_STATUSES:
        post.moderation_status = {
            safety.SafetyAction.ALLOW: ModerationStatus.PUBLISHED,
            safety.SafetyAction.FLAG: ModerationStatus.FLAGGED,
            safety.SafetyAction.HOLD: ModerationStatus.HELD,
        }[verdict.action]
    post.disclosure_flagged = flagged
    post.safety_categories = verdict.categories
    post.safety_reason = verdict.reason if verdict.categories else None
    post.reviewed_by = None
    post.reviewed_at = None
    post.review_note = None
    if post.moderation_status == ModerationStatus.HELD:
        post.held_at = datetime.now(timezone.utc)

    # Vote-then-edit: rewriting a post after it has been voted on turns other
    # people's endorsement into an endorsement of something they never saw.
    # Reset the score and mark it edited rather than silently keeping the votes.
    had_votes = post.up_count + post.down_count > 0
    post.body = body.strip()
    post.title = (title or None) and title.strip()
    post.edited_at = datetime.now(timezone.utc)

    if had_votes:
        await db.execute(
            delete(Vote).where(Vote.target_type == VoteTarget.POST, Vote.target_id == post.id)
        )
        post.score = post.up_count = post.down_count = 0
        post.hot_rank = standing_svc.hot_rank(0, post.created_at)
        logger.info("post_votes_reset_on_edit", post_id=str(post.id))

    # Expressive reactions must not endorse text that was subsequently rewritten.
    from app.db.models.social_media import PostReaction
    await db.execute(delete(PostReaction).where(PostReaction.post_id == post.id))
    await db.commit()
    if had_votes:
        await standing_svc.recompute_standing(db, post.author_id)
    await db.refresh(post)
    return post


async def delete_post(db: AsyncSession, post: Post, actor: User) -> None:
    from app.db.models.user import UserRole

    if post.author_id != actor.id and actor.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your post")
    # Soft delete. Standing is computed over all authored items including deleted
    # ones, so removing a downvoted post hides it without laundering the score.
    post.deleted_at = datetime.now(timezone.utc)
    await db.commit()


# ── Comments ─────────────────────────────────────────────────────────────────

async def create_comment(
    db: AsyncSession, post: Post, author: User, body: str, parent_id: uuid.UUID | None
) -> PostComment:
    await assert_can_view(db, post, author)
    from app.services.social_media import normalize_mentions
    body = await normalize_mentions(db, body)
    if post.visibility == PostVisibility.PUBLIC:
        safety.require_public_text(body)
    if parent_id is not None:
        parent = await db.get(PostComment, parent_id)
        if parent is None or parent.post_id != post.id or parent.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent comment not found")
        if parent.parent_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Replies are limited to one level — reply to the top-level comment instead.",
            )

    comment = PostComment(
        post_id=post.id, author_id=author.id, parent_id=parent_id, body=body.strip()
    )
    db.add(comment)
    await db.execute(update(Post).where(Post.id == post.id).values(comment_count=Post.comment_count + 1))
    await db.commit()
    await db.refresh(comment)
    return comment


async def list_comments(db: AsyncSession, post: Post, sort: str = "best") -> list[PostComment]:
    order = {
        "best": PostComment.confidence.desc(),
        "new": PostComment.created_at.desc(),
        "top": PostComment.score.desc(),
    }.get(sort, PostComment.confidence.desc())

    return list((await db.execute(
        select(PostComment)
        .where(PostComment.post_id == post.id, PostComment.deleted_at.is_(None))
        .order_by(order, PostComment.created_at.asc())
        .limit(500)
    )).scalars().all())


async def delete_comment(db: AsyncSession, comment: PostComment, actor: User) -> None:
    from app.db.models.user import UserRole

    if comment.author_id != actor.id and actor.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your comment")
    result = await db.execute(update(PostComment).where(PostComment.id == comment.id, PostComment.deleted_at.is_(None)).values(deleted_at=datetime.now(timezone.utc)).returning(PostComment.post_id))
    parent_id = result.scalar_one_or_none()
    if parent_id is not None:
        await db.execute(update(Post).where(Post.id == parent_id).values(comment_count=func.greatest(0, Post.comment_count - 1)))
    await db.commit()


# ── Voting ───────────────────────────────────────────────────────────────────

async def cast_vote(
    db: AsyncSession,
    voter: User,
    target_type: VoteTarget,
    target_id: uuid.UUID,
    value: int,
) -> dict:
    """Cast, change or clear a vote. `value` of 0 removes an existing vote."""
    if value not in (-1, 0, 1):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vote must be -1, 0 or 1")

    target = (
        await db.get(Post, target_id) if target_type == VoteTarget.POST
        else await db.get(PostComment, target_id)
    )
    if target is None or target.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    parent_post = target if target_type == VoteTarget.POST else await db.get(Post, target.post_id)
    if parent_post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    await assert_can_view(db, parent_post, voter)

    # Self-voting. Also enforced nowhere else, so it is checked here and covered
    # by a test — a reputation system whose author can vote on themselves has no
    # meaning at all.
    if target.author_id == voter.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="You can't vote on your own content")

    if value == -1:
        stats = await standing_svc.get_standing(db, voter.id)
        if not stats["can_downvote"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Downvoting unlocks at {standing_svc.DOWNVOTE_MIN_STANDING} standing. "
                    "Upvoting is available from day one."
                ),
            )

    existing = await db.scalar(
        select(Vote).where(
            Vote.voter_id == voter.id,
            Vote.target_type == target_type,
            Vote.target_id == target_id,
        )
    )

    if value == 0:
        if existing:
            await db.delete(existing)
    elif existing:
        existing.value = value
    else:
        db.add(Vote(voter_id=voter.id, target_type=target_type, target_id=target_id, value=value))

    await db.flush()

    # Recount from the votes table rather than incrementing counters. Slower, and
    # correct — counter drift in a reputation system is indistinguishable from
    # manipulation once it happens.
    ups = await db.scalar(
        select(func.count()).select_from(Vote).where(
            Vote.target_type == target_type, Vote.target_id == target_id, Vote.value == 1)
    ) or 0
    downs = await db.scalar(
        select(func.count()).select_from(Vote).where(
            Vote.target_type == target_type, Vote.target_id == target_id, Vote.value == -1)
    ) or 0

    target.up_count, target.down_count, target.score = ups, downs, ups - downs
    if target_type == VoteTarget.POST:
        target.hot_rank = standing_svc.hot_rank(target.score, target.created_at)
    else:
        target.confidence = standing_svc.wilson_confidence(ups, downs)

    await db.commit()
    await standing_svc.recompute_standing(db, target.author_id)

    return {"score": target.score, "up_count": ups, "down_count": downs, "my_vote": value}


async def my_votes(
    db: AsyncSession, user: User, target_type: VoteTarget, target_ids: list[uuid.UUID]
) -> dict[str, int]:
    if not target_ids:
        return {}
    rows = (await db.execute(
        select(Vote.target_id, Vote.value).where(
            Vote.voter_id == user.id,
            Vote.target_type == target_type,
            Vote.target_id.in_(target_ids),
        )
    )).all()
    return {str(tid): val for tid, val in rows}


# ── Follows and saves ────────────────────────────────────────────────────────

async def follow(db: AsyncSession, follower: User, followee_id: uuid.UUID) -> bool:
    if follower.id == followee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You can't follow yourself")
    if await db.get(User, followee_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    existing = await db.scalar(
        select(Follow).where(Follow.follower_id == follower.id, Follow.followee_id == followee_id)
    )
    if existing:
        return False
    db.add(Follow(follower_id=follower.id, followee_id=followee_id))
    await db.commit()
    return True


async def unfollow(db: AsyncSession, follower: User, followee_id: uuid.UUID) -> None:
    await db.execute(
        delete(Follow).where(Follow.follower_id == follower.id, Follow.followee_id == followee_id)
    )
    await db.commit()


async def is_following(db: AsyncSession, follower_id: uuid.UUID, followee_id: uuid.UUID) -> bool:
    return await db.scalar(
        select(Follow.id).where(Follow.follower_id == follower_id, Follow.followee_id == followee_id)
    ) is not None


async def toggle_save(db: AsyncSession, user: User, post_id: uuid.UUID) -> bool:
    existing = await db.scalar(
        select(SavedPost).where(SavedPost.user_id == user.id, SavedPost.post_id == post_id)
    )
    if existing:
        await db.delete(existing)
        await db.commit()
        return False
    db.add(SavedPost(user_id=user.id, post_id=post_id))
    await db.commit()
    return True


async def list_saved(db: AsyncSession, user: User, limit: int = 20, offset: int = 0) -> list[Post]:
    return list((await db.execute(
        select(Post)
        .join(SavedPost, SavedPost.post_id == Post.id)
        .where(SavedPost.user_id == user.id, Post.deleted_at.is_(None),
               _visibility_filter(user, await _member_community_ids(db, user)))
        .order_by(SavedPost.created_at.desc())
        .limit(limit).offset(offset)
    )).scalars().all())


# ── Reporting and moderation ─────────────────────────────────────────────────

async def report_content(
    db: AsyncSession,
    reporter: User,
    target_type: VoteTarget,
    target_id: uuid.UUID,
    reason: ReportReason,
    detail: str | None = None,
) -> dict:
    """File a report against a post or comment.

    Reports queue content for human review; they do not remove it. A single
    report auto-hiding content would hand any member a veto over any other
    member's post. Volume is different — several independent reports is a
    stronger signal than one opinion — so at REPORTS_TO_HOLD the post is pulled
    for review.
    """
    target = (
        await db.get(Post, target_id) if target_type == VoteTarget.POST
        else await db.get(PostComment, target_id)
    )
    if target is None or target.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    parent_post = target if target_type == VoteTarget.POST else await db.get(Post, target.post_id)
    if parent_post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    await assert_can_view(db, parent_post, reporter)
    if target.author_id == reporter.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="You can't report your own content")

    existing = await db.scalar(
        select(ContentReport).where(
            ContentReport.reporter_id == reporter.id,
            ContentReport.target_type == target_type,
            ContentReport.target_id == target_id,
        )
    )
    if existing is not None:
        return {"reported": True, "already": True}

    db.add(ContentReport(
        reporter_id=reporter.id, target_type=target_type,
        target_id=target_id, reason=reason, detail=detail,
    ))

    held = False
    if target_type == VoteTarget.POST:
        count = (await db.scalar(
            select(func.count()).select_from(ContentReport).where(
                ContentReport.target_type == VoteTarget.POST,
                ContentReport.target_id == target_id,
                ContentReport.resolved_at.is_(None),
            )
        ) or 0) + 1
        target.report_count = count

        # Reports alleging real-world harm carry more weight than "spam" —
        # the downside of holding a spam post briefly is nothing, but the
        # downside of leaving harmful instructions up while a queue drains is not.
        threshold = 1 if reason in (ReportReason.HARMFUL, ReportReason.ILLEGAL) else REPORTS_TO_HOLD
        if count >= threshold and target.moderation_status in VISIBLE_STATUSES:
            target.moderation_status = ModerationStatus.HELD
            target.held_at = datetime.now(timezone.utc)
            target.safety_reason = f"held after {count} report(s): {reason.value}"
            held = True
            logger.warning("post_held_by_reports", post_id=str(target_id),
                           reports=count, reason=reason.value)

    await db.commit()
    return {"reported": True, "already": False, "held": held}


async def moderation_queue(
    db: AsyncSession, *, status_filter: ModerationStatus | None = None,
    limit: int = 50, offset: int = 0,
) -> list[Post]:
    """Posts awaiting a decision, oldest first — a review queue is a FIFO, not a
    feed. Someone whose legitimate post was held should not wait behind newer
    arrivals."""
    stmt = select(Post).where(Post.deleted_at.is_(None))
    stmt = stmt.where(
        Post.moderation_status == status_filter if status_filter
        else Post.moderation_status.in_((ModerationStatus.HELD, ModerationStatus.FLAGGED))
    )
    return list((await db.execute(
        stmt.order_by(Post.held_at.asc().nullslast(), Post.created_at.asc())
        .limit(limit).offset(offset)
    )).scalars().all())


async def review_post(
    db: AsyncSession, post: Post, admin: User, approve: bool, note: str | None = None
) -> Post:
    """An admin decision on held content.

    Only this path can move a post out of HELD. The classifier can take content
    down; only a person puts it back up.
    """
    post.moderation_status = ModerationStatus.APPROVED if approve else ModerationStatus.REJECTED
    post.reviewed_by = admin.id
    post.reviewed_at = datetime.now(timezone.utc)
    post.review_note = note

    await db.execute(
        ContentReport.__table__.update()
        .where(
            ContentReport.target_type == VoteTarget.POST,
            ContentReport.target_id == post.id,
            ContentReport.resolved_at.is_(None),
        )
        .values(resolved_at=datetime.now(timezone.utc), resolved_by=admin.id)
    )
    await db.commit()
    await db.refresh(post)
    logger.info("post_reviewed", post_id=str(post.id), approved=approve,
                admin_id=str(admin.id))
    return post
