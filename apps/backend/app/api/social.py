"""
Social feed API: posts, comments, votes, follows, profiles.

Authorization follows the platform convention: reads on authentication, writes on
verified KYC. Voting requires verified KYC too — a vote produces reputation, and
reputation a Sybil can mint is worse than none.

The one anonymous-reachable route is the public feed, and it returns the same
teaser-tier author summary as everywhere else (no emails — SAHA-016).
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.social import (
    AuthorSummary, CommentResponse, CreateCommentRequest, CreatePostRequest,
    DisclosureCheckRequest, DisclosureCheckResponse, ModerationRow, PostResponse,
    ProfileResponse, ReportRequest, ReportResponse, ReviewRequest,
    UpdatePostRequest, UpdateProfileRequest, VoteRequest, VoteResponse,
)
from app.core.audit import write_audit_log
from app.core.clientip import client_ip
from app.core.ratelimit import ANON_READ_LIMIT, VOTE_LIMIT, WRITE_LIMIT, limiter
from app.core.security import get_current_user, get_optional_user, require_admin, require_collaborator
from app.db.models.social import (
    ModerationStatus, Post, PostKind, PostVisibility, UserProfile, UserStanding, VoteTarget,
)
from app.db.models.user import User
from app.db.session import get_db
from app.services import social_media as media_svc
from app.db.models.social_media import PostMedia
from app.services import disclosure
from app.services import posts as post_svc
from app.services import profiles as profile_svc
from app.services import standing as standing_svc

router = APIRouter(prefix="/api/v1/social", tags=["social"])


# ── Response assembly ────────────────────────────────────────────────────────

async def _author_summaries(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, AuthorSummary]:
    if not ids:
        return {}
    users = (await db.execute(select(User).where(User.id.in_(ids)))).scalars().all()
    profiles = {
        p.user_id: p for p in
        (await db.execute(select(UserProfile).where(UserProfile.user_id.in_(ids)))).scalars().all()
    }
    standings = {
        s.user_id: s for s in
        (await db.execute(select(UserStanding).where(UserStanding.user_id.in_(ids)))).scalars().all()
    }
    out = {}
    for u in users:
        total = standings[u.id].total_standing if u.id in standings else 0
        out[u.id] = AuthorSummary(
            user_id=u.id,
            full_name=u.full_name,
            headline=profiles[u.id].headline if u.id in profiles else None,
            has_avatar=u.avatar_key is not None,
            standing=total,
            tier=standing_svc.tier_for(total),
        )
    return out


async def _render_posts(
    db: AsyncSession, rows: list[Post], viewer: User | None
) -> list[PostResponse]:
    authors = await _author_summaries(db, {p.author_id for p in rows})
    media_by_post = {}
    if rows:
        for media in (await db.execute(select(PostMedia).where(PostMedia.post_id.in_([p.id for p in rows])).order_by(PostMedia.position))).scalars():
            media_by_post.setdefault(media.post_id, []).append(media_svc.media_response(media))
    reactions, my_reactions = await media_svc.reaction_summary(db, [p.id for p in rows], viewer)
    from app.db.models.social import Follow
    followed = set((await db.execute(select(Follow.followee_id).where(Follow.follower_id == viewer.id, Follow.followee_id.in_([p.author_id for p in rows])))).scalars()) if viewer and rows else set()
    votes = (
        await post_svc.my_votes(db, viewer, VoteTarget.POST, [p.id for p in rows])
        if viewer else {}
    )
    saved: set[str] = set()
    if viewer:
        from app.db.models.social import SavedPost
        saved = {
            str(pid) for pid in (await db.execute(
                select(SavedPost.post_id).where(
                    SavedPost.user_id == viewer.id,
                    SavedPost.post_id.in_([p.id for p in rows]) if rows else False,
                )
            )).scalars().all()
        } if rows else set()

    # Build the response explicitly rather than model_validate-then-patch.
    # `author` is assembled here, not a column on Post, so validating the ORM
    # object first fails on a missing required field — which is precisely how
    # this shipped broken the first time.
    return [
        PostResponse(
            id=p.id,
            media=media_by_post.get(p.id, []),
            reactions=reactions.get(p.id, {}),
            my_reaction=my_reactions.get(p.id),
            is_following_author=p.author_id in followed,
            author=authors.get(p.author_id) or AuthorSummary(
                user_id=p.author_id, full_name="Unknown member"),
            kind=p.kind,
            visibility=p.visibility,
            community_id=p.community_id,
            title=p.title,
            body=p.body,
            link_url=p.link_url,
            listing_id=p.listing_id,
            resource_id=p.resource_id,
            score=p.score,
            up_count=p.up_count,
            down_count=p.down_count,
            comment_count=p.comment_count,
            my_vote=votes.get(str(p.id), 0),
            is_saved=str(p.id) in saved,
            moderation_status=p.moderation_status,
            edited_at=p.edited_at,
            created_at=p.created_at,
        )
        for p in rows
    ]


# ── Feed ─────────────────────────────────────────────────────────────────────

@router.get("/feed", response_model=list[PostResponse])
@limiter.limit(ANON_READ_LIMIT)
async def feed(
    request: Request,
    sort: str = Query(default="hot", pattern="^(hot|new|top)$"),
    kind: PostKind | None = None,
    community_id: uuid.UUID | None = None,
    following_only: bool = False,
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0, le=5000),
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
):
    """The main feed.

    `hot` uses Reddit's ranking: log-weighted score with a ~12.5-hour decay, so
    early votes matter most and nothing stays on top forever. Anonymous callers
    see public posts only — the visibility filter is applied in the query, not
    by post-filtering the results.
    """
    rows = await post_svc.list_feed(
        db, viewer, sort=sort, kind=kind, community_id=community_id,
        following_only=following_only, limit=limit, offset=offset, q=q,
    )
    return await _render_posts(db, rows, viewer)


@router.get("/saved", response_model=list[PostResponse])
async def saved_posts(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    viewer: User = Depends(get_current_user),
):
    return await _render_posts(db, await post_svc.list_saved(db, viewer, limit, offset), viewer)


# ── Disclosure pre-check ─────────────────────────────────────────────────────

@router.post("/disclosure-check", response_model=DisclosureCheckResponse)
@limiter.limit(WRITE_LIMIT)
async def disclosure_check(
    body: DisclosureCheckRequest,
    request: Request,
    _: User = Depends(get_current_user),
):
    """Check a draft for language that reads like unpublished technical disclosure.

    Runs in-process — the draft never leaves the trust boundary. Advisory only:
    the composer shows a warning and the member decides. See
    services/disclosure.py for why this is a warning and not a block.
    """
    assessment = disclosure.analyse(body.body, body.title)
    return DisclosureCheckResponse(
        risk=assessment["risk"],
        signals=assessment["signals"],
        warning=disclosure.warning_for(assessment, body.visibility.value),
    )


# ── Posts ────────────────────────────────────────────────────────────────────

@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(WRITE_LIMIT)
async def create_post(
    body: CreatePostRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    author: User = Depends(require_collaborator),
):
    post = await post_svc.create_post(
        db, author,
        body=body.body, title=body.title, kind=body.kind, visibility=body.visibility,
        community_id=body.community_id, link_url=body.link_url,
        listing_id=body.listing_id, resource_id=body.resource_id,
        acknowledged_disclosure=body.acknowledged_disclosure, media_ids=body.media_ids,
    )
    background_tasks.add_task(
        write_audit_log, action="social.post_created", user_id=author.id,
        resource_type="post", resource_id=post.id,
        ip_address=client_ip(request),
        metadata={
            "visibility": post.visibility.value,
            "kind": post.kind.value,
            # Recorded because it is the evidence trail if a dispute ever turns on
            # when something became public.
            "disclosure_flagged": post.disclosure_flagged,
        },
    )
    background_tasks.add_task(media_svc.notify_mentions, post.id, author.id, post.body)
    return (await _render_posts(db, [post], author))[0]


@router.get("/posts/{post_id}", response_model=PostResponse)
@limiter.limit(ANON_READ_LIMIT)
async def get_post(
    post_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
):
    post = await post_svc.get_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    await post_svc.assert_can_view(db, post, viewer)
    return (await _render_posts(db, [post], viewer))[0]


@router.patch("/posts/{post_id}", response_model=PostResponse)
@limiter.limit(WRITE_LIMIT)
async def edit_post(
    post_id: uuid.UUID,
    body: UpdatePostRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    author: User = Depends(require_collaborator),
):
    """Edit a post. Existing votes are cleared.

    Rewriting a post after people have voted turns their endorsement into an
    endorsement of something they never read. Resetting the score is the honest
    handling; keeping the votes would be a small forgery.
    """
    post = await post_svc.get_post(db, post_id)
    if post is None or post.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    post = await post_svc.edit_post(db, post, author, body.body, body.title, acknowledged_disclosure=body.acknowledged_disclosure)
    return (await _render_posts(db, [post], author))[0]


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    post = await post_svc.get_post(db, post_id)
    if post is None or post.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    await post_svc.delete_post(db, post, actor)
    background_tasks.add_task(
        write_audit_log, action="social.post_deleted", user_id=actor.id,
        resource_type="post", resource_id=post_id,
    )


@router.post("/posts/{post_id}/save")
@limiter.limit(WRITE_LIMIT)
async def toggle_save(
    post_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    viewer: User = Depends(get_current_user),
):
    post = await post_svc.get_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    await post_svc.assert_can_view(db, post, viewer)
    return {"saved": await post_svc.toggle_save(db, viewer, post_id)}


# ── Comments ─────────────────────────────────────────────────────────────────

@router.get("/posts/{post_id}/comments", response_model=list[CommentResponse])
@limiter.limit(ANON_READ_LIMIT)
async def list_comments(
    post_id: uuid.UUID,
    request: Request,
    sort: str = Query(default="best", pattern="^(best|new|top)$"),
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
):
    """Comments, ranked by Wilson lower bound at 80% confidence by default.

    `best` asks "given this sample, what's the pessimistic estimate of approval?"
    — so a 10↑/0↓ comment can outrank a 300↑/100↓ one. Raw score can't express
    that, which is why Reddit uses this and why we do.
    """
    post = await post_svc.get_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    await post_svc.assert_can_view(db, post, viewer)

    rows = await post_svc.list_comments(db, post, sort)
    authors = await _author_summaries(db, {c.author_id for c in rows})
    votes = (
        await post_svc.my_votes(db, viewer, VoteTarget.COMMENT, [c.id for c in rows])
        if viewer else {}
    )
    return [
        CommentResponse(
            id=c.id,
            post_id=c.post_id,
            author=authors.get(c.author_id) or AuthorSummary(
                user_id=c.author_id, full_name="Unknown member"),
            parent_id=c.parent_id,
            body=c.body,
            score=c.score,
            up_count=c.up_count,
            down_count=c.down_count,
            confidence=c.confidence,
            my_vote=votes.get(str(c.id), 0),
            edited_at=c.edited_at,
            created_at=c.created_at,
        )
        for c in rows
    ]


@router.post("/posts/{post_id}/comments", response_model=CommentResponse,
             status_code=status.HTTP_201_CREATED)
@limiter.limit(WRITE_LIMIT)
async def create_comment(
    post_id: uuid.UUID,
    body: CreateCommentRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    author: User = Depends(require_collaborator),
):
    post = await post_svc.get_post(db, post_id)
    if post is None or post.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    await post_svc.assert_can_view(db, post, author)

    comment = await post_svc.create_comment(db, post, author, body.body, body.parent_id)
    background_tasks.add_task(media_svc.notify_mentions, post.id, author.id, comment.body)

    if post.author_id != author.id:
        from app.services import notifications as notif_svc
        background_tasks.add_task(
            notif_svc.notify_best_effort, post.author_id,
            "social.comment", "New comment on your post",
            f"{author.full_name} commented on your post.",
            f"/dashboard/feed/{post.id}",
        )

    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author=(await _author_summaries(db, {author.id}))[author.id],
        parent_id=comment.parent_id,
        body=comment.body,
        score=comment.score,
        up_count=comment.up_count,
        down_count=comment.down_count,
        confidence=comment.confidence,
        my_vote=0,
        edited_at=comment.edited_at,
        created_at=comment.created_at,
    )


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    from app.db.models.social import PostComment

    comment = await db.get(PostComment, comment_id)
    if comment is None or comment.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    await post_svc.delete_comment(db, comment, actor)


# ── Voting ───────────────────────────────────────────────────────────────────

@router.post("/posts/{post_id}/vote", response_model=VoteResponse)
@limiter.limit(VOTE_LIMIT)
async def vote_post(
    post_id: uuid.UUID,
    body: VoteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    voter: User = Depends(require_collaborator),
):
    """Vote on a post. Verified members only.

    A vote is what produces reputation, so the Sybil gate has to sit here rather
    than on reading. Self-voting is refused; downvoting unlocks at 50 standing.
    """
    return VoteResponse(**await post_svc.cast_vote(db, voter, VoteTarget.POST, post_id, body.value))


@router.post("/comments/{comment_id}/vote", response_model=VoteResponse)
@limiter.limit(VOTE_LIMIT)
async def vote_comment(
    comment_id: uuid.UUID,
    body: VoteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    voter: User = Depends(require_collaborator),
):
    return VoteResponse(**await post_svc.cast_vote(db, voter, VoteTarget.COMMENT, comment_id, body.value))


# ── Follows ──────────────────────────────────────────────────────────────────

@router.post("/members/{user_id}/follow")
@limiter.limit(WRITE_LIMIT)
async def follow_member(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    viewer: User = Depends(get_current_user),
):
    return {"following": await post_svc.follow(db, viewer, user_id)}


@router.delete("/members/{user_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_member(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    viewer: User = Depends(get_current_user),
):
    await post_svc.unfollow(db, viewer, user_id)


# ── Profiles ─────────────────────────────────────────────────────────────────

@router.get("/profiles/{user_id}", response_model=ProfileResponse)
async def get_profile(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    viewer: User = Depends(get_current_user),
):
    """A member's profile.

    The response separates `verified` (platform-derived: KYC, completed deals,
    ratings, listings) from `self_asserted` (headline, about, experience, skills).
    The frontend must render them as distinct sections — on a platform where a
    profile informs whether to trade IP, "they claim" and "we verified" cannot
    look the same.
    """
    data = await profile_svc.get_profile(db, user_id, viewer)
    data["recent_posts"] = await _render_posts(db, data["recent_posts"], viewer)
    return data


@router.patch("/profiles/me", response_model=ProfileResponse)
@limiter.limit(WRITE_LIMIT)
async def update_my_profile(
    body: UpdateProfileRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    viewer: User = Depends(get_current_user),
):
    changes = body.model_dump(exclude_unset=True, mode="json")
    await profile_svc.update_profile(db, viewer, changes)
    data = await profile_svc.get_profile(db, viewer.id, viewer)
    data["recent_posts"] = await _render_posts(db, data["recent_posts"], viewer)
    return data


# ── Reporting ────────────────────────────────────────────────────────────────

@router.post("/posts/{post_id}/report", response_model=ReportResponse)
@limiter.limit(WRITE_LIMIT)
async def report_post(
    post_id: uuid.UUID,
    body: ReportRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    reporter: User = Depends(get_current_user),
):
    """Report a post for review.

    Reports queue content for a human; they do not remove it. One member should
    not be able to unilaterally silence another. Reports alleging real-world harm
    are the exception — those pull the post immediately, because the cost of
    leaving harmful instructions up while a queue drains is not symmetric with
    the cost of holding a legitimate post for a few hours.
    """
    result = await post_svc.report_content(
        db, reporter, VoteTarget.POST, post_id, body.reason, body.detail
    )
    background_tasks.add_task(
        write_audit_log, action="social.content_reported", user_id=reporter.id,
        resource_type="post", resource_id=post_id,
        ip_address=client_ip(request),
        metadata={"reason": body.reason.value, "held": result.get("held", False)},
    )
    return ReportResponse(**result)


@router.post("/comments/{comment_id}/report", response_model=ReportResponse)
@limiter.limit(WRITE_LIMIT)
async def report_comment(
    comment_id: uuid.UUID,
    body: ReportRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    reporter: User = Depends(get_current_user),
):
    result = await post_svc.report_content(
        db, reporter, VoteTarget.COMMENT, comment_id, body.reason, body.detail
    )
    background_tasks.add_task(
        write_audit_log, action="social.content_reported", user_id=reporter.id,
        resource_type="comment", resource_id=comment_id,
        metadata={"reason": body.reason.value},
    )
    return ReportResponse(**result)


# ── Moderation (admin) ───────────────────────────────────────────────────────

@router.get("/moderation/queue", response_model=list[ModerationRow])
async def moderation_queue(
    status_filter: ModerationStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Posts awaiting a decision, oldest first.

    A review queue is a FIFO, not a feed — someone whose legitimate post was held
    should not wait behind newer arrivals.
    """
    rows = await post_svc.moderation_queue(db, status_filter=status_filter, limit=limit, offset=offset)
    attachments = {}
    if rows:
        for item in (await db.execute(select(PostMedia).where(PostMedia.post_id.in_([p.id for p in rows])).order_by(PostMedia.position))).scalars():
            attachments.setdefault(item.post_id, []).append(media_svc.media_response(item))
    authors = await _author_summaries(db, {p.author_id for p in rows})
    return [
        ModerationRow(
            id=p.id, author_id=p.author_id,
            author_name=authors[p.author_id].full_name if p.author_id in authors else "Unknown",
            media=attachments.get(p.id, []),
            title=p.title, body=p.body, visibility=p.visibility,
            moderation_status=p.moderation_status,
            safety_categories=list(p.safety_categories or []),
            safety_reason=p.safety_reason, report_count=p.report_count,
            held_at=p.held_at, created_at=p.created_at,
        )
        for p in rows
    ]


@router.post("/moderation/posts/{post_id}/review", response_model=ModerationRow)
async def review_post(
    post_id: uuid.UUID,
    body: ReviewRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Approve or reject held content.

    This is the ONLY path out of HELD. The classifier can take content down;
    only a person puts it back up. The asymmetry is deliberate — a wrongly-held
    post costs a delay, a wrongly-published one may not be recoverable.
    """
    post = await post_svc.get_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    post = await post_svc.review_post(db, post, admin, body.approve, body.note)

    background_tasks.add_task(
        write_audit_log,
        action="social.moderation_approved" if body.approve else "social.moderation_rejected",
        user_id=admin.id, resource_type="post", resource_id=post_id,
        metadata={
            "categories": list(post.safety_categories or []),
            "note": body.note,
            "author_id": str(post.author_id),
        },
    )
    from app.services import notifications as notif_svc
    background_tasks.add_task(
        notif_svc.notify, post.author_id,
        "social.moderation",
        "Your post was approved" if body.approve else "Your post wasn't approved",
        ("It's now visible to others." if body.approve
         else (body.note or "It didn't meet the content policy.")),
        f"/dashboard/feed/{post.id}" if body.approve else "/dashboard/feed",
    )

    authors = await _author_summaries(db, {post.author_id})
    return ModerationRow(
        id=post.id, author_id=post.author_id,
        author_name=authors[post.author_id].full_name if post.author_id in authors else "Unknown",
        title=post.title, body=post.body, visibility=post.visibility,
        moderation_status=post.moderation_status,
        safety_categories=list(post.safety_categories or []),
        safety_reason=post.safety_reason, report_count=post.report_count,
        held_at=post.held_at, created_at=post.created_at,
    )
