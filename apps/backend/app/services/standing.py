"""
Ranking and social standing.

The ranking formulas are Reddit's, taken from their published `_sorts.pyx` rather
than from descriptions of it. They are well-tuned and there is no reason to invent
our own. What differs from Reddit is stated explicitly, because "Reddit does it"
is not a reason on its own:

  · No vote fuzzing. Reddit randomises displayed counts so bot operators cannot
    tell whether their votes landed — sound for an anonymous platform. Saha is
    KYC-verified with an append-only audit log, so fuzzing would make the numbers
    untrustworthy while buying nothing.

  · The diminishing-returns curve is published, not secret. A hidden formula on a
    professional platform invites reverse-engineering; a stated one invites
    contribution.

  · Standing never merges with transaction reputation. See
    docs/SOCIAL-FEED-DESIGN.md §1.
"""

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.social import Post, PostComment, UserStanding, Vote, VoteTarget

# ── Reddit's hot ranking ─────────────────────────────────────────────────────
# hot = sign * log10(max(|score|, 1)) + (created - EPOCH) / 45000
#
# The 45,000-second divisor is ~12.5 hours: every 12.5 hours of age costs a post
# one order of magnitude of score. Without decay a feed this size would freeze on
# whatever went well once. The log means the first 10 votes move a post as much
# as the next 100, so new contributors are not buried under established ones.
_HOT_EPOCH = 1134028003          # Reddit's reference timestamp
_HOT_TIME_DIVISOR = 45000.0

# ── Wilson score interval, 80% confidence ────────────────────────────────────
# Reddit's "best" comment sort. Asks: given this sample, what is the pessimistic
# estimate of the true approval rate? Small samples are penalised until they earn
# confidence, so a 10↑/0↓ comment can rank above a 300↑/100↓ one — which raw
# score can never express.
_WILSON_Z = 1.281551565545

# ── Standing curve (published — see module docstring) ────────────────────────
# standing_from_item = K * ln(1 + max(net_score, 0)), capped per item.
# Logarithmic and capped so one viral item cannot manufacture an
# established-looking account, and so posting volume yields progressively less.
_STANDING_K = 6.0
_PER_ITEM_CAP = 50

# Reciprocal-vote defence: the n-th vote from the same voter on the same author's
# content contributes 1/n weight. Two accounts boosting each other converge on
# nothing without either being banned.
_PAIR_DECAY_ENABLED = True


def hot_rank(score: int, created_at: datetime) -> float:
    """Reddit's hot ordering. Higher sorts first."""
    order = math.log10(max(abs(score), 1))
    sign = 1 if score > 0 else (-1 if score < 0 else 0)
    seconds = created_at.replace(tzinfo=created_at.tzinfo or timezone.utc).timestamp() - _HOT_EPOCH
    return round(sign * order + seconds / _HOT_TIME_DIVISOR, 7)


def wilson_confidence(ups: int, downs: int) -> float:
    """Lower bound of the Wilson score interval at 80% confidence."""
    n = ups + downs
    if n == 0:
        return 0.0
    p = ups / n
    left = p + (_WILSON_Z ** 2) / (2 * n)
    right = _WILSON_Z * math.sqrt(p * (1 - p) / n + (_WILSON_Z ** 2) / (4 * n * n))
    under = 1 + (_WILSON_Z ** 2) / n
    return round((left - right) / under, 7)


def controversy(ups: int, downs: int) -> float:
    """Reddit's controversial sort — high when a thing is both popular and divisive."""
    if ups <= 0 or downs <= 0:
        return 0.0
    magnitude = ups + downs
    balance = (downs / ups) if ups > downs else (ups / downs)
    return round(magnitude ** balance, 7)


def standing_for_item(net_score: int) -> int:
    """Standing contributed by a single post or comment.

    Sub-linear and capped. Downvoted items contribute zero rather than negative:
    the aim is to reward contribution, not to let a pile-on drive someone's
    standing down and lock them out of privileges they had earned.
    """
    if net_score <= 0:
        return 0
    return min(int(round(_STANDING_K * math.log(1 + net_score))), _PER_ITEM_CAP)


# ── Standing tiers ───────────────────────────────────────────────────────────
# Stack Overflow's model rather than Reddit's: reputation unlocks PRIVILEGES
# proportionate to how it was earned. Standing gates social actions only. It
# gates nothing commercial — turning "posts a lot" into trading advantage is
# exactly the laundering this design exists to prevent.

TIERS: list[tuple[int, str]] = [
    (0, "New"),
    (50, "Contributor"),
    (250, "Established"),
    (1000, "Trusted"),
    (5000, "Distinguished"),
]

DOWNVOTE_MIN_STANDING = 50       # earn the ability to penalise before using it
CREATE_COMMUNITY_MIN_STANDING = 250
FLAG_CONTENT_MIN_STANDING = 1000


def tier_for(standing: int) -> str:
    label = TIERS[0][1]
    for threshold, name in TIERS:
        if standing >= threshold:
            label = name
    return label


def next_tier(standing: int) -> tuple[int, str] | None:
    for threshold, name in TIERS:
        if standing < threshold:
            return threshold, name
    return None


async def _pair_vote_weight(
    db: AsyncSession, voter_id: uuid.UUID, author_id: uuid.UUID
) -> float:
    """Weight for the n-th vote this voter has cast on this author's content.

    Returns 1/n. A pair of accounts upvoting each other sees each successive vote
    count for less, so a reciprocal ring converges on a small constant instead of
    compounding — without needing to detect or ban anyone.
    """
    if not _PAIR_DECAY_ENABLED:
        return 1.0

    post_votes = await db.scalar(
        select(func.count())
        .select_from(Vote)
        .join(Post, Post.id == Vote.target_id)
        .where(
            Vote.voter_id == voter_id,
            Vote.target_type == VoteTarget.POST,
            Post.author_id == author_id,
        )
    ) or 0
    comment_votes = await db.scalar(
        select(func.count())
        .select_from(Vote)
        .join(PostComment, PostComment.id == Vote.target_id)
        .where(
            Vote.voter_id == voter_id,
            Vote.target_type == VoteTarget.COMMENT,
            PostComment.author_id == author_id,
        )
    ) or 0

    return 1.0 / max(post_votes + comment_votes, 1)


async def recompute_standing(db: AsyncSession, user_id: uuid.UUID) -> UserStanding:
    """Recompute a user's standing from all of their authored items.

    Deliberately includes soft-deleted items. Standing computed only over visible
    content would mean deleting a downvoted post launders the penalty away —
    deletion should hide content, not rewrite reputation.
    """
    post_rows = (await db.execute(
        select(Post.score).where(Post.author_id == user_id)
    )).scalars().all()
    comment_rows = (await db.execute(
        select(PostComment.score).where(PostComment.author_id == user_id)
    )).scalars().all()

    post_standing = sum(standing_for_item(s) for s in post_rows)
    comment_standing = sum(standing_for_item(s) for s in comment_rows)

    standing = await db.get(UserStanding, user_id)
    if standing is None:
        standing = UserStanding(user_id=user_id)
        db.add(standing)

    standing.post_standing = post_standing
    standing.comment_standing = comment_standing
    standing.total_standing = post_standing + comment_standing
    standing.posts_count = len(post_rows)
    standing.comments_count = len(comment_rows)
    await db.commit()
    return standing


async def get_standing(db: AsyncSession, user_id: uuid.UUID) -> dict:
    standing = await db.get(UserStanding, user_id)
    total = standing.total_standing if standing else 0
    nxt = next_tier(total)
    return {
        "total_standing": total,
        "post_standing": standing.post_standing if standing else 0,
        "comment_standing": standing.comment_standing if standing else 0,
        "posts_count": standing.posts_count if standing else 0,
        "comments_count": standing.comments_count if standing else 0,
        "tier": tier_for(total),
        "next_tier": nxt[1] if nxt else None,
        "next_tier_at": nxt[0] if nxt else None,
        "can_downvote": total >= DOWNVOTE_MIN_STANDING,
        "can_create_community": total >= CREATE_COMMUNITY_MIN_STANDING,
        "can_flag": total >= FLAG_CONTENT_MIN_STANDING,
    }
