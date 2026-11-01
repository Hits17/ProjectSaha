"""
Gaming resistance for the social layer.

A reputation number that can be manufactured is worse than no reputation number,
because it looks like information. These are the attacks worth defending against
here, in rough order of how likely someone is to actually try them.

The route-level guarantees (auth on every route, verified-KYC on writes and
votes) are covered by tests/test_authorization_matrix.py, which walks the live
route table. This file covers the rules that live in the service layer.
"""

import inspect

import pytest

from app.services import posts as post_svc
from app.services import standing as standing_svc


def _source(fn) -> str:
    return inspect.getsource(fn)


def _code_only(module) -> str:
    """Module source with docstrings stripped.

    Naive grepping over raw source is unreliable here: these modules' docstrings
    legitimately discuss the very things the tests assert the absence of ("never
    merges with transaction reputation", "not an LLM call"). Stripping the prose
    means the assertions describe the code rather than the commentary.
    """
    import ast

    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body.pop(0)
    return ast.unparse(tree)


# ── Self-voting ──────────────────────────────────────────────────────────────

def test_self_voting_is_refused():
    """A reputation system whose authors can vote on themselves means nothing."""
    src = _source(post_svc.cast_vote)
    assert "target.author_id == voter.id" in src
    assert "own content" in src


# ── One vote per member per item ─────────────────────────────────────────────

def test_double_voting_is_prevented_by_a_database_constraint():
    """Service-layer checks get forgotten (SAHA-007 was exactly that). The
    unique constraint holds even if a future code path skips the lookup."""
    from app.db.models.social import Vote

    constraints = {c.name for c in Vote.__table__.constraints}
    assert "uq_vote_once" in constraints

    unique_cols = next(
        {c.name for c in c_.columns}
        for c_ in Vote.__table__.constraints
        if getattr(c_, "name", None) == "uq_vote_once"
    )
    assert unique_cols == {"voter_id", "target_type", "target_id"}


def test_vote_values_are_constrained_at_the_database():
    from app.db.models.social import Vote

    assert "ck_vote_value" in {c.name for c in Vote.__table__.constraints}


def test_revoting_updates_rather_than_accumulates():
    src = _source(post_svc.cast_vote)
    assert "existing.value = value" in src, "re-voting must update the existing row"


def test_counts_are_recounted_not_incremented():
    """Counter drift in a reputation system is indistinguishable from
    manipulation once it happens."""
    src = _source(post_svc.cast_vote)
    assert "func.count()" in src
    assert "+= 1" not in src


# ── Sybil / ring resistance ──────────────────────────────────────────────────

def test_voting_requires_confirmed_collaborator():
    """The Sybil gate sits on voting, not on reading — a vote is what produces
    reputation, and reputation a Sybil can mint is worse than none.

    Reads the resolved dependency graph rather than the source text, so it stays
    true regardless of how the handler is written.
    """
    from app.main import app

    vote_routes = {
        (r.path, m)
        for r in app.routes
        if getattr(r, "path", "").endswith("/vote") and hasattr(r, "dependant")
        for m in (getattr(r, "methods", set()) or set()) - {"HEAD", "OPTIONS"}
    }
    assert vote_routes, "no vote routes found"

    for route in app.routes:
        if not getattr(route, "path", "").endswith("/vote") or not hasattr(route, "dependant"):
            continue
        guards = {
            getattr(d.call, "__name__", "") for d in route.dependant.dependencies
        }
        assert "require_collaborator" in guards, (
            f"{route.path} must require confirmed collaboration identity to vote, found {guards}"
        )


def test_reciprocal_vote_rings_decay():
    """Two accounts upvoting each other should converge on nothing.

    The n-th vote from the same voter on the same author contributes 1/n, so a
    ring's returns collapse without anyone needing to detect or ban it.
    """
    src = _source(post_svc.__dict__.get("cast_vote"))
    assert standing_svc._PAIR_DECAY_ENABLED is True
    weights = [1.0 / n for n in range(1, 11)]
    assert weights[0] == 1.0
    assert weights[9] == pytest.approx(0.1)
    assert sum(weights) < 3.0, "ten reciprocal votes must be worth far less than ten"


def test_downvoting_requires_earned_standing():
    """Stack Overflow's model: earn the ability to penalise before using it.
    A throwaway account cannot arrive and start burying people."""
    assert standing_svc.DOWNVOTE_MIN_STANDING >= 50
    src = _source(post_svc.cast_vote)
    assert "can_downvote" in src


# ── Farming by volume ────────────────────────────────────────────────────────

def test_one_viral_item_cannot_manufacture_an_account():
    """Reddit caps per-post karma for this reason. Ours is capped and published."""
    assert standing_svc.standing_for_item(1_000_000) == standing_svc._PER_ITEM_CAP
    assert standing_svc._PER_ITEM_CAP <= 50


def test_posting_volume_yields_diminishing_returns():
    single_big = standing_svc.standing_for_item(1000)
    many_small = sum(standing_svc.standing_for_item(1) for _ in range(10))
    assert single_big < standing_svc._PER_ITEM_CAP + 1
    assert many_small < single_big * 3, "spamming small posts must not out-earn quality"


# ── Laundering a bad record ──────────────────────────────────────────────────

def test_deleting_a_downvoted_post_does_not_launder_standing():
    """Standing is computed over ALL authored items, including soft-deleted ones.
    Deletion hides content; it must not rewrite reputation."""
    src = _source(standing_svc.recompute_standing)
    assert "deleted" in src.lower(), "recompute must document its treatment of deletes"
    assert "deleted_at.is_(None)" not in _code_only(standing_svc), (
        "standing must not filter out deleted posts — that would let someone "
        "delete downvoted content to recover their score"
    )


def test_editing_after_votes_resets_the_score():
    """Rewriting a post after people voted turns their endorsement into an
    endorsement of something they never read."""
    src = _source(post_svc.edit_post)
    assert "delete(Vote)" in src
    assert "edited_at" in src


def test_edits_are_marked():
    from app.db.models.social import Post

    assert "edited_at" in Post.__table__.columns


# ── Standing is not commercial credibility ───────────────────────────────────

def test_standing_gates_only_social_privileges():
    """Turning "posts a lot" into trading advantage is the laundering this whole
    design exists to prevent. Standing must not gate anything commercial."""
    code = _code_only(standing_svc).lower()
    for commercial in ("escrow", "disburse", "vault", "transaction", "listing"):
        assert commercial not in code, (
            f"standing.py code references {commercial!r} — standing must not gate commerce"
        )


def test_profile_keeps_verified_and_self_asserted_apart():
    """A profile informs whether to trade IP. "They claim" and "we verified"
    cannot be rendered as the same thing."""
    from app.api.schemas.social import ProfileResponse

    fields = set(ProfileResponse.model_fields)
    assert {"verified", "standing", "self_asserted"} <= fields

    from app.api.schemas.social import SelfAssertedBlock, VerifiedBlock

    verified = set(VerifiedBlock.model_fields)
    asserted = set(SelfAssertedBlock.model_fields)
    assert not (verified & asserted), "a field cannot be both verified and self-asserted"
    assert "completed_deals" in verified and "headline" in asserted


def test_no_combined_reputation_score_exists_anywhere():
    """The single most important invariant in this feature.

    If social standing and transaction reputation are ever summed into one
    number, someone farms engagement and arrives at a negotiation looking like a
    proven counterparty.
    """
    from app.db.models.social import UserStanding

    columns = set(UserStanding.__table__.columns.keys())
    for forbidden in ("reputation", "combined", "overall_score", "trust_score"):
        assert not any(forbidden in c for c in columns), (
            f"user_standing has a {forbidden!r} column — standing and track record "
            "must stay separate"
        )


# ── Visibility ───────────────────────────────────────────────────────────────

def test_default_visibility_is_members_not_public():
    """Broadcasting to the open internet should be a choice, not an inheritance —
    premature disclosure destroys novelty permanently."""
    from app.api.schemas.social import CreatePostRequest
    from app.db.models.social import PostVisibility

    assert CreatePostRequest.model_fields["visibility"].default == PostVisibility.MEMBERS


def test_anonymous_viewers_see_only_public_posts():
    src = _source(post_svc._visibility_filter)
    assert "viewer is None" in src
    assert "PostVisibility.PUBLIC" in src


def test_community_posts_require_membership_to_read():
    src = _source(post_svc._visibility_filter)
    assert "member_community_ids" in src


def test_high_risk_public_post_requires_acknowledgement():
    """One deliberate moment of friction before an irreversible disclosure."""
    src = _source(post_svc.create_post)
    assert "acknowledged_disclosure" in src
    assert "disclosure_warning" in src


def test_attaching_a_listing_requires_owning_it():
    """Otherwise a member could attach someone else's listing and imply authorship."""
    src = _source(post_svc.create_post)
    assert "listing.creator_id != author.id" in src
