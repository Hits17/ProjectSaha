"""
Social layer: posts, comments, votes, profiles and standing.

Design notes live in docs/SOCIAL-FEED-DESIGN.md. Two decisions are load-bearing
enough to restate here, because both are easy to undo by accident:

1. `user_standing` (social) and transaction reviews (track record) are SEPARATE
   and are never summed. Standing is cheap to earn; a completed deal is not.
   Merging them would let someone farm engagement and arrive at a negotiation
   looking like a proven counterparty.

2. `visibility` defaults to MEMBERS, not PUBLIC. This platform's premise is that
   premature disclosure destroys novelty permanently, so broadcasting to the open
   internet should be a choice someone makes, not a default they inherit.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, Enum as SAEnum, Float,
    ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class PostVisibility(str, enum.Enum):
    PUBLIC = "public"        # anyone, including unauthenticated
    MEMBERS = "members"      # any signed-in member — the default
    COMMUNITY = "community"  # one community's members only


class PostKind(str, enum.Enum):
    UPDATE = "update"        # "here's what I'm working on"
    QUESTION = "question"    # asking the network
    SHOWCASE = "showcase"    # finished work, usually with an attachment


class VoteTarget(str, enum.Enum):
    POST = "post"
    COMMENT = "comment"


class ModerationStatus(str, enum.Enum):
    """Where a post sits in the safety pipeline.

    PUBLISHED is the normal state. HELD means the safety classifier or a member
    report took it out of circulation pending human review — it is invisible to
    everyone except its author and admins. REJECTED and REMOVED are terminal.

    Nothing is auto-published out of HELD: a classifier can take content down but
    only a person puts it back up. That asymmetry is deliberate — the cost of a
    wrongly-held post is a delay, the cost of a wrongly-published one is not
    recoverable.
    """

    PUBLISHED = "published"
    FLAGGED = "flagged"    # visible, but queued for review
    HELD = "held"          # NOT visible; awaiting admin decision
    APPROVED = "approved"  # a human reviewed and cleared it
    REJECTED = "rejected"  # a human reviewed and refused it
    REMOVED = "removed"    # taken down after publication


class ReportReason(str, enum.Enum):
    HARMFUL = "harmful"            # weapons, poisons, instructions for harm
    ILLEGAL = "illegal"
    HARASSMENT = "harassment"
    SPAM = "spam"
    CONFIDENTIAL = "confidential"  # discloses someone else's IP
    OTHER = "other"


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    visibility: Mapped[PostVisibility] = mapped_column(
        SAEnum(PostVisibility, name="post_visibility", create_type=False,
               values_callable=lambda o: [e.value for e in o]),
        nullable=False, default=PostVisibility.MEMBERS,
    )
    community_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE")
    )
    kind: Mapped[PostKind] = mapped_column(
        SAEnum(PostKind, name="post_kind", create_type=False,
               values_callable=lambda o: [e.value for e in o]),
        nullable=False, default=PostKind.UPDATE,
    )

    title: Mapped[str | None] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(1000))

    # Optional attachments. These are what make the feed Saha's rather than a
    # generic timeline — "here's what I'm building" pointing at the actual asset.
    listing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ip_listings.id", ondelete="SET NULL"))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("open_resources.id", ondelete="SET NULL"))

    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    down_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Reddit's hot formula — see services/standing.py. Stored so the feed can be
    # ordered in the database rather than in Python.
    hot_rank: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)

    # Set when the composer's disclosure classifier fired and the author posted
    # anyway. Kept for the evidence trail, not shown to other members.
    disclosure_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Content safety ───────────────────────────────────────────────────────
    # A post only appears in the feed when moderation_status is PUBLISHED or
    # APPROVED. See services/safety.py for how the classifier decides, and note
    # that it can hold but never release — release requires a person.
    moderation_status: Mapped[ModerationStatus] = mapped_column(
        SAEnum(ModerationStatus, name="moderation_status", create_type=False,
               values_callable=lambda o: [e.value for e in o]),
        nullable=False, default=ModerationStatus.PUBLISHED, index=True,
    )
    safety_categories: Mapped[list[str]] = mapped_column(
        ARRAY(String), server_default="{}", nullable=False)
    safety_reason: Mapped[str | None] = mapped_column(String(500))
    held_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(String(1000))
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    comments: Mapped[list["PostComment"]] = relationship(
        "PostComment", back_populates="post", cascade="all, delete-orphan"
    )


class PostComment(Base):
    """One level of threading — a reply may have a parent, a reply to a reply may not.

    Deeper nesting is where discussion quality degrades on a network this size;
    the constraint is enforced in the service layer, not just by convention.
    """

    __tablename__ = "post_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("post_comments.id", ondelete="CASCADE"))

    body: Mapped[str] = mapped_column(Text, nullable=False)

    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    down_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Wilson lower bound at 80% confidence — Reddit's "best" sort. Ranks by the
    # pessimistic estimate of approval rate, so a 10↑/0↓ comment can outrank a
    # 300↑/100↓ one. Raw score cannot express that.
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    post: Mapped["Post"] = relationship("Post", back_populates="comments")


class Vote(Base):
    """One row per (voter, target). Attributable, not fuzzed.

    Reddit randomises displayed vote counts so bot operators can't tell whether
    their votes landed — a sound defence for an anonymous platform. Saha is
    KYC-verified with an append-only audit log, so fuzzing would make the numbers
    untrustworthy while buying nothing. The Sybil resistance fuzzing approximates,
    identity verification gives directly.
    """

    __tablename__ = "votes"
    __table_args__ = (
        UniqueConstraint("voter_id", "target_type", "target_id", name="uq_vote_once"),
        CheckConstraint("value IN (-1, 1)", name="ck_vote_value"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    voter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    target_type: Mapped[VoteTarget] = mapped_column(
        SAEnum(VoteTarget, name="vote_target", create_type=False,
               values_callable=lambda o: [e.value for e in o]),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserProfile(Base):
    """LinkedIn-style profile. Everything here is SELF-ASSERTED.

    Rendered visually below the verified block (KYC status, completed deals,
    published listings) precisely because it is unverified. On a platform where a
    profile informs whether to trade IP, the distinction between "they claim" and
    "we verified" has to be visible, not implied.
    """

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    headline: Mapped[str | None] = mapped_column(String(220))     # LinkedIn's limit
    about: Mapped[str | None] = mapped_column(String(2600))       # LinkedIn's limit
    location: Mapped[str | None] = mapped_column(String(120))
    website_url: Mapped[str | None] = mapped_column(String(500))
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}", nullable=False)
    # [{"title","organization","start","end","description"}]
    experience: Mapped[list | None] = mapped_column(JSONB)
    # Pinned listings / library entries / posts — the LinkedIn "Featured" section.
    featured: Mapped[list | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserStanding(Base):
    """Derived social reputation. Recomputed from votes; never authoritative alone.

    Deliberately does NOT include transaction reputation. See the module docstring
    and docs/SOCIAL-FEED-DESIGN.md §1 — the separation is the whole point.
    """

    __tablename__ = "user_standing"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    post_standing: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    comment_standing: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_standing: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, index=True)
    posts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Follow(Base):
    """Directed follow edge. Follower counts are intentionally not exposed —
    see docs/SOCIAL-FEED-DESIGN.md §7."""

    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "followee_id", name="uq_follow_once"),
        CheckConstraint("follower_id <> followee_id", name="ck_no_self_follow"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    follower_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    followee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SavedPost(Base):
    __tablename__ = "saved_posts"
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_saved_once"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ContentReport(Base):
    """A member flagging a post or comment.

    Reports are advisory — they queue content for human review rather than
    removing it, because a report button that auto-hides is a heckler's veto.
    The exception is volume: several independent reports on one item escalate it
    to HELD, since that is a stronger signal than any single opinion.
    """

    __tablename__ = "content_reports"
    __table_args__ = (
        UniqueConstraint("reporter_id", "target_type", "target_id", name="uq_report_once"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    target_type: Mapped[VoteTarget] = mapped_column(
        SAEnum(VoteTarget, name="vote_target", create_type=False,
               values_callable=lambda o: [e.value for e in o]),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    reason: Mapped[ReportReason] = mapped_column(
        SAEnum(ReportReason, name="report_reason", create_type=False,
               values_callable=lambda o: [e.value for e in o]),
        nullable=False,
    )
    detail: Mapped[str | None] = mapped_column(String(1000))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
