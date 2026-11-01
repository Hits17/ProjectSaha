"""
Composer disclosure guard.

Saha's premise is that public disclosure destroys patent novelty permanently. A
feed whose purpose is encouraging members to post about what they're working on
cuts against that, so the composer warns before a public post that reads like
unpublished technical detail.

The hard requirement is BALANCE. A guard that fires on every post trains people
to dismiss it, which is worse than having none — so the false-positive tests
below matter as much as the detection ones.

It warns and never blocks: the member owns their disclosure decision.
"""

import inspect

import pytest

from app.services import disclosure


def _risk(body, title=None):
    return disclosure.analyse(body, title)["risk"]


# ── Should warn ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "We're the first in the world to get this reaction working at scale.",
    "Nobody has done this before — our secret sauce is the ligand choice.",
    "This is our proprietary process for the coating, unpublished so far.",
    "Holding off posting details until before we file the provisional.",
    "Patent pending, but here's the gist of how it works.",
    "We haven't filed yet so I'll keep it vague.",
])
def test_novelty_and_filing_language_warns(text):
    assert _risk(text) == "high", text


def test_process_parameters_with_a_process_verb_warns():
    assert _risk(
        "We catalyse the reaction at 80 °C for 45 min using a 3 wt% palladium loading."
    ) == "high"


def test_composition_detail_warns():
    assert _risk(
        "The blend consists of 40 wt% PLA and 12 wt% plasticiser, extruded at 190 °C."
    ) in ("high", "low")


def test_title_is_scanned_too():
    assert _risk("Just an update", title="Our proprietary formulation, unpublished") == "high"


# ── Should NOT warn — the tests that keep this usable ────────────────────────

@pytest.mark.parametrize("text", [
    "Shipped the new dashboard this week. Feedback welcome.",
    "Looking for a manufacturing partner in the EU for a class II device.",
    "We closed our first licensing deal on the platform today.",
    "Anyone dealt with CIPO assignment recordation? Took 30 days for us.",
    "Our lead time is 45 days and MOQ is 500 units.",
    "Just published a listing for an expired patent we're productising.",
    "Great discussion in the materials science community this morning.",
    "The standard is ISO 9001 and we test to ASTM A36.",
])
def test_ordinary_business_posts_do_not_warn(text):
    assert _risk(text) == "none", f"false positive: {text}"


def test_a_lone_number_is_not_a_disclosure():
    """"Ships in 30 days" is not a method. Parameters only count alongside a
    process verb — that pairing is what keeps this from firing constantly."""
    assert _risk("It ships in 30 days and costs 500 USD per unit.") == "none"


def test_empty_input_is_safe():
    assert _risk("") == "none"
    assert _risk("   \n ") == "none"


# ── Warning behaviour ────────────────────────────────────────────────────────

def test_warning_only_shown_for_public_posts():
    """A members-only post is still a disclosure, but the audience is
    KYC-verified. Warning on every draft would train people to dismiss it."""
    risky = disclosure.analyse("Our secret formula uses a novel catalyst.")
    assert disclosure.warning_for(risky, "public") is not None
    assert disclosure.warning_for(risky, "members") is None
    assert disclosure.warning_for(risky, "community") is None


def test_no_warning_when_there_is_no_risk():
    assert disclosure.warning_for(disclosure.analyse("Shipped a thing."), "public") is None


def test_warning_names_the_actual_consequence():
    warning = disclosure.warning_for(
        disclosure.analyse("Our unpublished process runs at 200 °C, we catalyse it."), "public"
    )
    assert "novelty" in warning.lower()
    assert "public" in warning.lower()


def test_signals_explain_why_it_fired():
    """A warning the member can't act on is noise."""
    result = disclosure.analyse("Nobody has done this. We sinter at 900 °C for 3 hours.")
    assert result["signals"]
    for signal in result["signals"]:
        assert signal["code"] and signal["label"] and signal["hint"]


# ── Structural guarantees ────────────────────────────────────────────────────

def test_classifier_makes_no_network_call():
    """Sending post drafts to a third-party inference API to check whether they
    contain trade secrets would be self-defeating. Same reasoning as SAHA-013.

    Checks imports and executable code rather than raw source — the module
    docstring legitimately contains the words it is asserting the absence of.
    """
    import ast

    tree = ast.parse(inspect.getsource(disclosure))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    for forbidden in ("httpx", "requests", "openai", "anthropic", "aiohttp", "urllib"):
        assert forbidden not in imported, (
            f"disclosure.py imports {forbidden!r} — this must run in-process"
        )
    assert not any(
        isinstance(n, (ast.AsyncFunctionDef, ast.Await)) for n in ast.walk(tree)
    ), "disclosure.py has async code — it should be a pure in-process function"


def test_it_warns_rather_than_blocks():
    """analyse() returns an assessment. Nothing here raises or refuses — the
    decision belongs to the member."""
    signature = inspect.signature(disclosure.analyse)
    assert "raise" not in inspect.getsource(disclosure.analyse)
    assert len(signature.parameters) == 2
