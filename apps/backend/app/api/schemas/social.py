import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models.social import ModerationStatus, PostKind, PostVisibility, ReportReason

MAX_BODY = 10_000
MAX_COMMENT = 5_000


def _clean_url(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if not v.startswith(("https://", "http://")):
        raise ValueError("Links must start with http:// or https://")
    return v


# ── Posts ────────────────────────────────────────────────────────────────────

class CreatePostRequest(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_BODY)
    title: str | None = Field(default=None, max_length=300)
    kind: PostKind = PostKind.UPDATE
    # Defaults to MEMBERS, never PUBLIC. Broadcasting to the open internet should
    # be a choice someone makes, not one they inherit — see the model docstring.
    visibility: PostVisibility = PostVisibility.MEMBERS
    community_id: uuid.UUID | None = None
    link_url: str | None = Field(default=None, max_length=1000)
    listing_id: uuid.UUID | None = None
    resource_id: uuid.UUID | None = None
    # Set by the composer once the member has seen and dismissed the disclosure
    # warning. The API refuses a high-risk public post without it.
    acknowledged_disclosure: bool = False
    media_ids: list[uuid.UUID] = Field(default_factory=list, max_length=6)

    @field_validator("link_url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        return _clean_url(v)

    @field_validator("body")
    @classmethod
    def _body_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Post body cannot be empty")
        return v


class UpdatePostRequest(BaseModel):
    acknowledged_disclosure: bool = False
    body: str = Field(min_length=1, max_length=MAX_BODY)
    title: str | None = Field(default=None, max_length=300)


class AuthorSummary(BaseModel):
    """Author identity as shown on a post. Deliberately no email — see SAHA-016."""

    user_id: uuid.UUID
    full_name: str
    headline: str | None = None
    has_avatar: bool = False
    standing: int = 0
    tier: str = "New"


class MediaResponse(BaseModel):
    id: uuid.UUID
    content_type: str
    byte_size: int
    alt_text: str
    position: int
    url: str


class PostResponse(BaseModel):
    media: list[MediaResponse] = Field(default_factory=list)
    reactions: dict[str, int] = Field(default_factory=dict)
    my_reaction: str | None = None
    is_following_author: bool = False
    id: uuid.UUID
    author: AuthorSummary
    kind: PostKind
    visibility: PostVisibility
    community_id: uuid.UUID | None
    title: str | None
    body: str
    link_url: str | None
    listing_id: uuid.UUID | None
    resource_id: uuid.UUID | None
    score: int
    up_count: int
    down_count: int
    comment_count: int
    my_vote: int = 0
    is_saved: bool = False
    # Surfaced so the author can see their own post is held rather than watching
    # it silently vanish. Other members never receive a held post at all.
    moderation_status: ModerationStatus = ModerationStatus.PUBLISHED
    edited_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Comments ─────────────────────────────────────────────────────────────────

class CreateCommentRequest(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_COMMENT)
    parent_id: uuid.UUID | None = None

    @field_validator("body")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Comment cannot be empty")
        return v


class CommentResponse(BaseModel):
    id: uuid.UUID
    post_id: uuid.UUID
    author: AuthorSummary
    parent_id: uuid.UUID | None
    body: str
    score: int
    up_count: int
    down_count: int
    confidence: float
    my_vote: int = 0
    edited_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Votes ────────────────────────────────────────────────────────────────────

class VoteRequest(BaseModel):
    value: int = Field(ge=-1, le=1, description="1 upvote, -1 downvote, 0 clears")


class ReportRequest(BaseModel):
    reason: ReportReason
    detail: str | None = Field(default=None, max_length=1000)


class ReportResponse(BaseModel):
    reported: bool
    already: bool = False
    held: bool = False


class ModerationRow(BaseModel):
    """A held or flagged post as the admin console sees it."""

    id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    media: list[MediaResponse] = Field(default_factory=list)
    title: str | None
    body: str
    visibility: PostVisibility
    moderation_status: ModerationStatus
    safety_categories: list[str] = []
    safety_reason: str | None
    report_count: int
    held_at: datetime | None
    created_at: datetime


class ReviewRequest(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=1000)


class VoteResponse(BaseModel):
    score: int
    up_count: int
    down_count: int
    my_vote: int


# ── Disclosure pre-check ─────────────────────────────────────────────────────

class DisclosureCheckRequest(BaseModel):
    body: str = Field(max_length=MAX_BODY)
    title: str | None = Field(default=None, max_length=300)
    visibility: PostVisibility = PostVisibility.MEMBERS


class DisclosureSignalOut(BaseModel):
    code: str
    label: str
    hint: str


class DisclosureCheckResponse(BaseModel):
    risk: str
    signals: list[DisclosureSignalOut] = []
    warning: str | None = None


# ── Profiles ─────────────────────────────────────────────────────────────────

class ExperienceEntry(BaseModel):
    title: str = Field(max_length=200)
    organization: str | None = Field(default=None, max_length=200)
    start: str | None = Field(default=None, max_length=32)
    end: str | None = Field(default=None, max_length=32)
    description: str | None = Field(default=None, max_length=2000)


class FeaturedEntry(BaseModel):
    kind: str = Field(max_length=32)          # listing | resource | post | link
    ref_id: str | None = Field(default=None, max_length=64)
    label: str = Field(max_length=200)
    url: str | None = Field(default=None, max_length=1000)


class UpdateProfileRequest(BaseModel):
    headline: str | None = Field(default=None, max_length=220)   # LinkedIn's limit
    about: str | None = Field(default=None, max_length=2600)     # LinkedIn's limit
    location: str | None = Field(default=None, max_length=120)
    website_url: str | None = Field(default=None, max_length=500)
    skills: list[str] | None = None
    experience: list[ExperienceEntry] | None = None
    featured: list[FeaturedEntry] | None = None

    @field_validator("website_url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        return _clean_url(v)


class VerifiedBlock(BaseModel):
    """Platform-derived. Nothing here can be self-reported."""

    kyc_verified: bool
    member_since: datetime
    completed_deals: int
    average_rating: float | None
    review_count: int
    published_listings: int
    library_contributions: int
    communities: int


class StandingBlock(BaseModel):
    """Social standing. Never summed with the track record above."""

    total_standing: int
    post_standing: int
    comment_standing: int
    posts_count: int
    comments_count: int
    tier: str
    next_tier: str | None
    next_tier_at: int | None
    can_downvote: bool
    can_create_community: bool
    can_flag: bool


class SelfAssertedBlock(BaseModel):
    headline: str | None
    about: str | None
    location: str | None
    website_url: str | None
    skills: list[str] = []
    experience: list[dict] = []
    featured: list[dict] = []


class ProfileResponse(BaseModel):
    user_id: uuid.UUID
    full_name: str
    role: str
    has_avatar: bool
    verified: VerifiedBlock
    standing: StandingBlock
    self_asserted: SelfAssertedBlock
    recent_posts: list[PostResponse] = []
    is_following: bool = False
    is_self: bool = False
