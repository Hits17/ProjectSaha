"""
Ranking and standing.

The formulas are Reddit's, so these tests assert the *properties* that make them
the right choice rather than re-deriving the arithmetic. A test that only checks
`hot(10, t) == 1.234` tells you nothing when someone changes the constant; a test
that checks "early votes matter more than late ones" catches it.
"""

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.services import standing as s


def _t(hours_ago: float = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours_ago)


# ── Hot ranking ──────────────────────────────────────────────────────────────

def test_higher_score_ranks_higher_at_equal_age():
    now = _t()
    assert s.hot_rank(100, now) > s.hot_rank(10, now)


def test_newer_ranks_higher_at_equal_score():
    assert s.hot_rank(10, _t(0)) > s.hot_rank(10, _t(24))


def test_vote_weight_is_logarithmic():
    """The first 10 votes should move a post about as much as the next 90.

    This is what stops established accounts burying newcomers, and it is the
    single most important property of the hot formula.
    """
    now = _t()
    first_ten = s.hot_rank(10, now) - s.hot_rank(1, now)
    next_ninety = s.hot_rank(100, now) - s.hot_rank(10, now)
    assert first_ten == pytest.approx(next_ninety, rel=0.01)


def test_age_decays_by_one_order_of_magnitude_per_12_5_hours():
    """A post 12.5h older needs ~10x the score to hold the same position."""
    old = s.hot_rank(100, _t(12.5))
    new = s.hot_rank(10, _t(0))
    assert new == pytest.approx(old, abs=0.02)


def test_negative_score_sinks_below_zero_score():
    now = _t()
    assert s.hot_rank(-50, now) < s.hot_rank(0, now) < s.hot_rank(50, now)


def test_hot_handles_zero_without_error():
    assert isinstance(s.hot_rank(0, _t()), float)


# ── Wilson confidence ────────────────────────────────────────────────────────

def test_small_confident_sample_beats_large_mediocre_one():
    """The reason we don't rank comments by raw score.

    10↑/0↓ is better evidence of quality than 300↑/100↓, even though the latter
    has a far higher net score.
    """
    assert s.wilson_confidence(10, 0) > s.wilson_confidence(300, 100)


def test_confidence_rises_with_sample_size_at_equal_ratio():
    assert s.wilson_confidence(100, 0) > s.wilson_confidence(10, 0)


def test_confidence_is_zero_with_no_votes():
    assert s.wilson_confidence(0, 0) == 0.0


def test_confidence_is_bounded():
    assert 0.0 <= s.wilson_confidence(1000, 0) <= 1.0
    assert 0.0 <= s.wilson_confidence(1, 1000) <= 1.0


def test_downvoted_comment_scores_near_zero():
    assert s.wilson_confidence(1, 50) < 0.05


# ── Controversy ──────────────────────────────────────────────────────────────

def test_controversy_peaks_when_votes_are_split():
    split = s.controversy(100, 100)
    lopsided = s.controversy(200, 1)
    assert split > lopsided


def test_controversy_is_zero_without_opposition():
    assert s.controversy(100, 0) == 0.0
    assert s.controversy(0, 100) == 0.0


# ── Standing curve ───────────────────────────────────────────────────────────

def test_standing_has_diminishing_returns():
    """One viral post must not manufacture an established-looking account."""
    ten = s.standing_for_item(10)
    hundred = s.standing_for_item(100)
    thousand = s.standing_for_item(1000)
    assert ten < hundred < thousand
    assert (hundred - ten) > (thousand - hundred)


def test_standing_is_capped_per_item():
    assert s.standing_for_item(10_000_000) == s._PER_ITEM_CAP


def test_downvoted_item_contributes_zero_not_negative():
    """A pile-on should not strip privileges someone already earned."""
    assert s.standing_for_item(-100) == 0
    assert s.standing_for_item(0) == 0


def test_standing_matches_the_published_formula():
    """The curve is documented in the UI, so it has to match what we publish."""
    for score in (1, 5, 25, 100):
        assert s.standing_for_item(score) == min(
            int(round(s._STANDING_K * math.log(1 + score))), s._PER_ITEM_CAP
        )


# ── Tiers and privileges ─────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    (0, "New"), (49, "New"), (50, "Contributor"), (249, "Contributor"),
    (250, "Established"), (999, "Established"), (1000, "Trusted"),
    (4999, "Trusted"), (5000, "Distinguished"), (100000, "Distinguished"),
])
def test_tier_boundaries(value, expected):
    assert s.tier_for(value) == expected


def test_new_members_can_upvote_but_not_downvote():
    """Stack Overflow's model: earn the ability to penalise before using it."""
    assert s.DOWNVOTE_MIN_STANDING > 0
    assert s.tier_for(0) == "New"


def test_next_tier_guides_progress():
    threshold, name = s.next_tier(10)
    assert threshold == 50 and name == "Contributor"
    assert s.next_tier(999_999) is None


def test_privilege_thresholds_are_ordered():
    assert (
        s.DOWNVOTE_MIN_STANDING
        < s.CREATE_COMMUNITY_MIN_STANDING
        < s.FLAG_CONTENT_MIN_STANDING
    )


# ── The separation that matters most ─────────────────────────────────────────

def test_standing_module_never_reads_transaction_reputation():
    """Social standing and trading track record must not merge.

    Standing is cheap to earn. A completed deal is not. If the two were summed,
    someone could farm engagement and arrive at a negotiation looking like a
    proven counterparty — which is the specific failure this design exists to
    prevent (docs/SOCIAL-FEED-DESIGN.md §1).
    """
    import inspect

    source = inspect.getsource(s)
    for forbidden in ("Review", "Transaction", "average_rating", "completed_deals"):
        assert forbidden not in source, (
            f"standing.py references {forbidden!r} — social standing must stay "
            "independent of transaction reputation"
        )
