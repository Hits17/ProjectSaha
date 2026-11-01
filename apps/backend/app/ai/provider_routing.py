"""
Per-function default AI provider mapping.

This file is the only place that decides "which provider for which job".
The legal assistant is hardcoded to Anthropic — non-negotiable.
"""

from app.core.config import settings


def _provider_enum():
    from app.ai.client import Provider
    return Provider


FUNCTION_PROVIDER_MAP = {
    # Legal — ALWAYS Anthropic. Do not change this.
    "legal_concept_assistant": "anthropic",
    "contract_review": "anthropic",

    # Discovery — fast, cheap, NVIDIA is fine
    "discovery_intent_parse": "nvidia",
    "discovery_comparison": "nvidia",

    # BOM dialogue — multi-turn, NVIDIA is fine for dev
    "bom_creator_dialogue": "nvidia",
    "bom_manufacturer_procurement": "nvidia",

    # Contact detection — small task
    "contact_detection_classifier": "nvidia",

    # Demand signal aggregation — batch job
    "demand_signal_synthesis": "nvidia",
}

# Functions that must always use Anthropic regardless of global setting
_ALWAYS_ANTHROPIC = {"legal_concept_assistant", "contract_review"}

# ── Data-tier policy (security/AUDIT.md SAHA-013) ────────────────────────────
# Every AI call site is classified by the sensitivity of what it sends. Anything
# above `internal` must not leave the trust boundary for third-party inference:
# NVIDIA and Anthropic are external processors in other jurisdictions, with no
# DPA, no user disclosure and no residency control.
#
# `bom_creator_dialogue` is the sharpest case — it carries the transcript in
# which a creator describes their unpublished invention. That is the single most
# valuable asset on the platform, and it was being POSTed to a public API.
#
# Ollama runs locally, so confidential tiers route there. If no local provider is
# reachable the call fails closed rather than silently falling back to an
# external one: a failed AI feature is recoverable, a disclosed trade secret is not.
TRADE_SECRET = "trade_secret"
CONFIDENTIAL = "confidential"
INTERNAL = "internal"

FUNCTION_DATA_TIER = {
    "bom_creator_dialogue": TRADE_SECRET,
    "bom_manufacturer_procurement": TRADE_SECRET,
    "legal_concept_assistant": CONFIDENTIAL,
    "contract_review": CONFIDENTIAL,
    "contact_detection_classifier": CONFIDENTIAL,
    "discovery_intent_parse": INTERNAL,
    "discovery_comparison": INTERNAL,
    "demand_signal_synthesis": INTERNAL,
}

_LOCAL_ONLY_TIERS = {TRADE_SECRET, CONFIDENTIAL}


def requires_local_inference(function_name: str) -> bool:
    tier = FUNCTION_DATA_TIER.get(function_name, CONFIDENTIAL)  # unknown ⇒ treat as sensitive
    return tier in _LOCAL_ONLY_TIERS and not settings.ALLOW_EXTERNAL_LLM_FOR_CONFIDENTIAL


def _anthropic_available() -> bool:
    key = settings.ANTHROPIC_API_KEY
    return bool(key) and not key.startswith("sk-ant-REPLACE")


def get_provider_for_function(function_name: str):
    """
    Returns the Provider enum for a given function name.

    Resolution order:
    - Data-tier policy wins over everything: confidential and trade-secret
      functions route to the self-hosted provider unless explicitly overridden
    - If function is in _ALWAYS_ANTHROPIC AND Anthropic key is configured: use Anthropic
    - If function is in _ALWAYS_ANTHROPIC but key is missing: fall through to global setting
    - If global LLM_PROVIDER is 'anthropic': force everything to Anthropic
    - If global is 'nvidia' or 'ollama': use that for all functions
    - If global is 'auto': use FUNCTION_PROVIDER_MAP
    """
    from app.ai.client import Provider

    if requires_local_inference(function_name):
        return Provider.OLLAMA

    if function_name in _ALWAYS_ANTHROPIC and _anthropic_available():
        return Provider.ANTHROPIC

    global_setting = settings.LLM_PROVIDER

    if global_setting == "anthropic":
        return Provider.ANTHROPIC

    if global_setting in ("nvidia", "ollama"):
        return Provider(global_setting)

    # auto — use per-function map
    mapped = FUNCTION_PROVIDER_MAP.get(function_name)
    if mapped:
        return Provider(mapped)

    return None
