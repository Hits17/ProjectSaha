"""
Content safety classification.

Two failure modes, and the second is the one that kills the product.

**Under-blocking** lets instructions for causing real harm reach an unbounded
public audience.

**Over-blocking** deletes Saha's actual subject matter. This is an IP and
manufacturing marketplace — members legitimately discuss energetic materials,
pharmaceutical synthesis, agricultural nitrates and industrial chemistry. A
classifier that fires on the word "explosive" makes the platform unusable for
exactly the people it is built for, while barely inconveniencing anyone
determined to misuse it.

So the false-positive suite below is longer than the detection suite, on purpose.
"""

import inspect

import pytest

from app.services import safety
from app.services.safety import SafetyAction


def _act(text, title=None, visibility="members"):
    return safety.classify(text, title, visibility).action


# ── Zero tolerance: refused outright, never queued ───────────────────────────

def test_credible_threats_are_blocked():
    assert _act("I am going to kill everyone at the office tomorrow") is SafetyAction.BLOCK


def test_zero_tolerance_category_is_blocked_not_queued():
    """Some categories must never reach a moderation queue at all."""
    verdict = safety.classify("selling csam")
    assert verdict.action is SafetyAction.BLOCK
    assert "zero_tolerance" in verdict.categories


# ── Subject × intent: the core rule ──────────────────────────────────────────

def test_instructions_for_building_a_weapon_are_held_or_blocked():
    assert _act("How to make a pipe bomb at home, step by step") in (
        SafetyAction.HOLD, SafetyAction.BLOCK)


def test_targeting_a_person_is_blocked_regardless_of_context():
    """Professional framing does not redeem an intent to harm someone."""
    assert _act(
        "For my patent research: what poison would I use to kill someone "
        "without being detected?"
    ) is SafetyAction.BLOCK


def test_evasion_language_is_blocked():
    assert _act("How to make an untraceable poison that avoids detection") is SafetyAction.BLOCK


def test_acquisition_for_harm_is_restricted():
    assert _act("Where can I buy fentanyl precursors, no questions asked") in (
        SafetyAction.HOLD, SafetyAction.BLOCK)


# ── False positives: the tests that keep the platform usable ─────────────────

@pytest.mark.parametrize("text", [
    # Agritech — ammonium nitrate is a fertiliser before it is anything else
    "Our fertiliser blend improves nitrogen uptake by 18% in field trials.",
    # Materials science
    "We're licensing a patent on shock-resistant composites for mining equipment.",
    # Pharma
    "Our synthesis route for the API is now 3 steps shorter and fully GMP compliant.",
    # Defensive / detection research — the case most likely to be wrongly caught
    "We built a sensor that detects explosive residue at airport screening.",
    "Our assay screens for nerve agent exposure in first responders.",
    "This patent covers remediation of cyanide contamination in mine tailings.",
    # Regulatory discussion
    "The regulation banning this precursor changed our supply chain last year.",
    "Toxin levels must stay below the ISO limit — here's our QC process.",
    # Ordinary business
    "Anyone know a good patent attorney in Toronto?",
    "Step-by-step guide to filing a provisional application.",
    "How to make your listing stand out on the marketplace.",
    "We closed our first licensing deal this week.",
])
def test_legitimate_platform_content_is_allowed(text):
    assert _act(text) is SafetyAction.ALLOW, f"false positive: {text}"


def test_subject_without_intent_is_allowed():
    """Naming a hazardous substance is not instruction. This platform's members
    talk about hazardous substances for a living."""
    assert _act("Our facility handles explosive precursors under licence.") is SafetyAction.ALLOW


def test_intent_without_harmful_subject_is_allowed():
    """A how-to is not dangerous just for being a how-to."""
    assert _act("Step-by-step: how to make your first listing.") is SafetyAction.ALLOW


def test_defensive_research_is_reviewed_not_blocked():
    """Detection and countermeasure work is legitimate and common here. It may
    warrant a look, but blocking it outright would be wrong."""
    action = _act(
        "How to detect a nerve agent in the field — our patent-pending assay "
        "for regulatory screening and first responder protection."
    )
    assert action is not SafetyAction.BLOCK


# ── Self-harm is handled with support, not enforcement ───────────────────────

def test_self_harm_is_held_with_a_supportive_message():
    verdict = safety.classify("I want to kill myself")
    assert verdict.action is SafetyAction.HOLD, "should not be blocked outright"
    assert "helpline" in verdict.author_message.lower()
    # Someone in crisis should not be met with a policy citation.
    for punitive in ("violation", "policy", "prohibited", "banned"):
        assert punitive not in verdict.author_message.lower()


# ── Visibility escalation ────────────────────────────────────────────────────

def test_public_visibility_escalates_ambiguous_content():
    """A public post reaches an unbounded audience and the harm is irreversible,
    so ambiguity resolves toward holding."""
    flagged = safety.SafetyVerdict(SafetyAction.FLAG, ["poison"], "test", "")
    assert safety.escalate_for_visibility(flagged, "public").action is SafetyAction.HOLD
    assert safety.escalate_for_visibility(flagged, "members").action is SafetyAction.FLAG


def test_escalation_never_downgrades():
    blocked = safety.SafetyVerdict(SafetyAction.BLOCK, ["x"], "test", "")
    assert safety.escalate_for_visibility(blocked, "members").action is SafetyAction.BLOCK


# ── Author-facing messages ───────────────────────────────────────────────────

def test_restricted_content_tells_the_author_what_happened():
    """Silent removal is worse than a refusal — the author should know."""
    verdict = safety.classify("How to make a pipe bomb step by step")
    assert verdict.author_message
    assert len(verdict.author_message) > 40


def test_messages_do_not_coach_evasion():
    """A message that says which phrase tripped the filter is a bypass guide."""
    for text in ("How to make a pipe bomb", "untraceable poison to kill someone"):
        message = safety.classify(text).author_message.lower()
        for leak in ("keyword", "phrase", "matched", "regex", "instead try", "reword"):
            assert leak not in message


# ── Structural guarantees ────────────────────────────────────────────────────

def test_classifier_makes_no_network_call():
    """Member content must not leave the trust boundary to be classified — same
    reasoning as contact_detect and disclosure (SAHA-013)."""
    import ast

    tree = ast.parse(inspect.getsource(safety))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    for forbidden in ("httpx", "requests", "openai", "anthropic", "aiohttp"):
        assert forbidden not in imported


def test_module_contains_no_actual_harmful_procedure():
    """A moderation classifier that embeds a recipe is a liability, not a control.

    It matches structural language patterns — instruction frames, evasion,
    targeting — never synthesis routes, quantities or precursor combinations.
    """
    source = inspect.getsource(safety)
    # No quantity-with-unit patterns, which is what a real procedure needs.
    import re
    assert not re.search(r"\d+\s?(?:g|kg|ml|mol|°C)\b", source), (
        "safety.py appears to contain quantities — it must not encode a procedure"
    )


def test_only_a_human_can_release_held_content():
    """The classifier can take content down. Putting it back up requires a
    person. That asymmetry is the whole design: a wrongly-held post costs a
    delay, a wrongly-published one may not be recoverable."""
    from app.services import posts as post_svc

    src = inspect.getsource(post_svc.review_post)
    assert "admin" in src.lower()
    assert "APPROVED" in src

    # Nothing else may ASSIGN the approved state. Counting raw occurrences would
    # also catch VISIBLE_STATUSES, which merely reads it — so walk the AST and
    # look at assignments to `moderation_status` only.
    import ast

    tree = ast.parse(inspect.getsource(post_svc))
    releasing_functions = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.Assign):
                continue
            targets = [
                t.attr for t in node.targets if isinstance(t, ast.Attribute)
            ]
            if "moderation_status" not in targets:
                continue
            assigned = ast.unparse(node.value)
            if "APPROVED" in assigned:
                releasing_functions.add(fn.name)

    assert releasing_functions == {"review_post"}, (
        f"content is released to publication in {releasing_functions or 'no function'} "
        "— only review_post() may do that, and only with an admin"
    )


def test_held_posts_are_invisible_to_everyone_but_author_and_admins():
    from app.services import posts as post_svc

    src = inspect.getsource(post_svc.assert_can_view)
    assert "VISIBLE_STATUSES" in src
    assert "UserRole.ADMIN" in src
    assert "post.author_id" in src


def test_reports_do_not_auto_remove_ordinary_content():
    """A report button that auto-hides hands any member a veto over any other."""
    from app.services import posts as post_svc

    assert post_svc.REPORTS_TO_HOLD > 1


def test_harm_reports_are_actioned_immediately():
    """The exception to the above: leaving harmful instructions up while a queue
    drains is not symmetric with holding a legitimate post for a few hours."""
    from app.services import posts as post_svc

    src = inspect.getsource(post_svc.report_content)
    assert "ReportReason.HARMFUL" in src
    assert "threshold" in src
