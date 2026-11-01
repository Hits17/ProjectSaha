"""
Regression suite for SAHA-013 — negotiation plaintext sent to a third-party LLM.

The contact-info classifier used to POST the **full plaintext of every
negotiation message** to NVIDIA's inference API to answer a yes/no question.
Negotiation content on this platform carries valuation, licensing strategy and
trade secrets, so the platform was spending a confidential disclosure per message
to run a rule-expressible check — and messages were AES-encrypted at rest
*after* their plaintext had already left the trust boundary.

The replacement is deterministic and in-process. These tests exist because the
LLM version could not be tested at all: its answers were neither stable nor
offline-reproducible.

`test_classifier_needs_no_network` is the important one — it proves the
confidential path is gone, not merely discouraged.
"""

import pytest

from app.services.contact_detect import contains_contact_info, detect


@pytest.mark.parametrize("text,reason", [
    ("email me at john@example.com", "email_address"),
    ("John.Doe+saha@sub.example.co.uk please", "email_address"),
    ("reach me: john (at) example (dot) com", "email_address"),
    ("john at example dot com", "email_address"),
    ("call me on +1 415 555 0132", "phone_number"),
    ("my cell is 415-555-0132", "phone_number"),
    ("ring four one five five five five zero one three two", "phone_number"),
    ("ping me on WhatsApp", "messaging_platform"),
    ("here's my telegram", "messaging_platform"),
    ("book time via calendly", "messaging_platform"),
    ("see https://example.com/deal", "external_url"),
    ("go to www.example.com", "external_url"),
    ("our site is example.com", "external_url"),
    ("find me @johndoe", "social_handle"),
])
def test_detects_contact_details(text, reason):
    found, why = detect(text)
    assert found, f"missed: {text}"
    assert why == reason


@pytest.mark.parametrize("text", [
    "We can offer an exclusive licence for the EU territory.",
    "Our BOM calls for 4 carbide inserts and 1 tool steel blank per unit.",
    "The patent US4503000A expired in 2003 and is public domain.",
    "Batch size is 500 units; lead time 30 days.",
    "Quantity per unit is 0.6 m of preloaded 20mm linear rail.",
    "Standard ISO 9001 applies; see ASTM A36 for the steel grade.",
    "Can we close by 2026-09-30?",
    "We'd want a 24 month term with a 5% running royalty.",
])
def test_does_not_flag_ordinary_negotiation(text):
    assert not contains_contact_info(text), f"false positive: {text}"


def test_zero_width_obfuscation_is_caught():
    """Someone trying to move a deal off-platform will try this."""
    assert contains_contact_info("john​@​example.com")


def test_spaced_letter_obfuscation_is_caught():
    assert contains_contact_info("j o h n at example dot com")


def test_empty_and_whitespace_are_safe():
    assert not contains_contact_info("")
    assert not contains_contact_info("   \n\t ")


def test_classifier_needs_no_network(monkeypatch):
    """The whole point: this must work with the LLM client unreachable.

    If this test ever fails, message plaintext is leaving the trust boundary
    again.
    """
    import app.ai.client as ai_client

    async def _explode(*args, **kwargs):
        raise AssertionError("contact detection must never call an LLM")

    monkeypatch.setattr(ai_client.llm, "complete", _explode)
    assert contains_contact_info("mail me at a@b.com") is True
    assert contains_contact_info("we propose a non-exclusive licence") is False


def test_messages_service_does_not_import_the_llm_client():
    """Structural guard — the import itself is the risk surface."""
    import inspect

    from app.services import messages

    source = inspect.getsource(messages)
    assert "llm" not in source, (
        "app.services.messages must not reference the LLM client: message "
        "plaintext is trade-secret-adjacent (security/AUDIT.md SAHA-013)"
    )


def test_ai_routing_keeps_confidential_functions_local(monkeypatch):
    from app.ai.client import Provider
    from app.ai.provider_routing import get_provider_for_function
    from app.core.config import settings

    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_LLM_FOR_CONFIDENTIAL", False)
    for fn in ("bom_creator_dialogue", "contact_detection_classifier",
               "legal_concept_assistant", "bom_manufacturer_procurement"):
        assert get_provider_for_function(fn) is Provider.OLLAMA, (
            f"{fn} handles confidential content and must not route externally"
        )


def test_unknown_ai_function_is_treated_as_confidential(monkeypatch):
    """Fail closed: a new call site nobody classified must not default to an
    external provider."""
    from app.ai.client import Provider
    from app.ai.provider_routing import get_provider_for_function
    from app.core.config import settings

    monkeypatch.setattr(settings, "ALLOW_EXTERNAL_LLM_FOR_CONFIDENTIAL", False)
    assert get_provider_for_function("some_new_feature_nobody_classified") is Provider.OLLAMA
