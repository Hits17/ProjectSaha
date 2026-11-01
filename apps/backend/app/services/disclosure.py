"""
Novelty-risk detection for the post composer.

Why this exists
---------------
Saha's premise is that disclosing an invention publicly destroys its novelty
permanently and in every jurisdiction — that is the whole reason the vault, the
tiered listing disclosure and the NDA roadmap exist. A feed whose explicit
purpose is encouraging members to post about what they are working on cuts
directly against that.

That is not a reason to skip the feature. It is a reason to put one moment of
friction in front of it.

What this is NOT
----------------
* Not a blocker. It warns; the member decides. A false positive must never stop
  someone posting, and the member owns their own disclosure decision.
* Not legal advice. It cannot tell you whether something is patentable, only that
  the text pattern-matches unpublished technical detail.
* Not an LLM call. Same reasoning as services/contact_detect.py — sending post
  drafts to a third-party inference API to check whether they contain trade
  secrets would be self-defeating. This runs in-process and nothing leaves the
  trust boundary.

Detection aims for the things people actually write when they are about to
disclose something they shouldn't: specific process parameters, explicit novelty
claims, and filing-status language.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DisclosureSignal:
    code: str
    label: str
    hint: str


# Explicit novelty / secrecy claims — the clearest signal that someone believes
# what they are describing is protectable.
_NOVELTY = re.compile(
    r"\b(?:"
    r"nobody(?:'s| has)? (?:ever )?(?:done|tried|made|built)"
    r"|first (?:ever )?(?:to|in the world)"
    r"|never been (?:done|tried|published|attempted)"
    r"|secret (?:sauce|recipe|formula|process|ingredient)"
    r"|proprietary (?:process|formula|method|blend|technique)"
    r"|our (?:breakthrough|novel|unique) (?:process|method|approach|formulation)"
    r"|trade secret"
    r"|unpublished"
    r")\b",
    re.I,
)

# Filing-status language — if someone is talking about filing, the timing of
# public disclosure is exactly what matters.
_FILING = re.compile(
    r"\b(?:"
    r"before we file|haven'?t filed|not yet filed|pre-?filing"
    r"|provisional(?: application| patent)?"
    r"|patent[- ]pending|filing (?:next|soon|this)"
    r"|priority date|grace period"
    r"|prior art search"
    r")\b",
    re.I,
)

# Process parameters: a number with a technical unit. One is unremarkable; a
# cluster of them alongside process verbs reads like a method disclosure.
_PARAMETER = re.compile(
    r"\b\d+(?:\.\d+)?\s?"
    r"(?:°\s?[CF]|deg(?:rees)?\s?[CF]?|K\b"
    r"|wt%|vol%|%\s?(?:w/w|v/v|by (?:weight|volume))|%"
    r"|m?g/(?:m?l|L|kg)|mol/L|M\b|mM|µM|nM"
    r"|MPa|kPa|bar|psi|atm"
    r"|rpm|Hz|kHz|kW|MW"
    r"|nm|µm|um|mm|cm\b"
    r"|min(?:utes?)?|hrs?|hours?"
    r")\b",
    re.I,
)

_PROCESS_VERB = re.compile(
    r"\b(?:"
    r"catalys[et]|catalytic|sinter|anneal|calcin|electrolys|electroplat"
    r"|polymeris|polymeriz|crosslink|cross-link|copolymer"
    r"|ferment|inoculat|culture[ds]?|incubat"
    r"|extrud|mould|mold|cure[ds]?|curing|vulcanis|vulcaniz"
    r"|dope[ds]?|doping|deposit|sputter|etch"
    r"|titrat|distil|reflux|precipitat|centrifug|chromatograph"
    r"|formulat|synthesis|synthesise|synthesize"
    r")\w*\b",
    re.I,
)

# Composition language — "X% of Y" style recipes.
_COMPOSITION = re.compile(
    r"\b(?:"
    r"consists? of|composed of|comprising|made (?:up )?of|blend of|ratio of"
    r"|parts? by (?:weight|volume)|w/w|v/v"
    r")\b",
    re.I,
)

_SIGNALS = {
    "novelty_claim": DisclosureSignal(
        "novelty_claim",
        "Novelty or secrecy claim",
        "You've described this as new, unique or secret. Public disclosure can "
        "start or forfeit patent filing windows depending on jurisdiction.",
    ),
    "filing_status": DisclosureSignal(
        "filing_status",
        "Filing-status language",
        "You've mentioned filing. If an application isn't on file yet, posting "
        "publicly may affect what you can still claim.",
    ),
    "process_parameters": DisclosureSignal(
        "process_parameters",
        "Specific process parameters",
        "Temperatures, concentrations, pressures or timings alongside process "
        "steps can amount to an enabling disclosure of a method.",
    ),
    "composition": DisclosureSignal(
        "composition",
        "Composition detail",
        "Ratios and constituent lists can disclose a formulation.",
    ),
}


def analyse(text: str, title: str | None = None) -> dict:
    """Return the disclosure risk assessment for a draft post.

    Shape:
        {"risk": "none"|"low"|"high", "signals": [{code,label,hint}, ...]}
    """
    blob = f"{title or ''}\n{text or ''}".strip()
    if not blob:
        return {"risk": "none", "signals": []}

    hits: list[str] = []

    if _NOVELTY.search(blob):
        hits.append("novelty_claim")
    if _FILING.search(blob):
        hits.append("filing_status")

    # A parameter alone is noise ("ships in 30 days"). A parameter next to a
    # process verb is a method. Requiring both is what keeps this usable.
    params = len(_PARAMETER.findall(blob))
    if params >= 2 and _PROCESS_VERB.search(blob):
        hits.append("process_parameters")
    if _COMPOSITION.search(blob) and params >= 1:
        hits.append("composition")

    if not hits:
        return {"risk": "none", "signals": []}

    # What makes a hit "high":
    #   · a novelty or filing claim — the member has told us they think this is
    #     protectable, which is the strongest signal available;
    #   · process parameters next to a process verb — temperatures, loadings and
    #     timings describing a method is an enabling disclosure, which is the
    #     thing that actually forfeits novelty;
    #   · any two signals together.
    high = (
        "novelty_claim" in hits
        or "filing_status" in hits
        or "process_parameters" in hits
        or len(hits) >= 2
    )
    return {
        "risk": "high" if high else "low",
        "signals": [
            {"code": s.code, "label": s.label, "hint": s.hint}
            for s in (_SIGNALS[h] for h in hits)
        ],
    }


def warning_for(assessment: dict, visibility: str) -> str | None:
    """The copy shown in the composer, or None when nothing should be shown.

    Only surfaced for genuinely public posts. A `members`-visibility post is
    still a disclosure in the legal sense, but the audience is KYC-verified and
    warning on every draft would train people to dismiss the warning — which is
    worse than not showing one.
    """
    if assessment["risk"] == "none" or visibility != "public":
        return None
    return (
        "This post may describe unpublished technical detail. Public posts are "
        "visible to anyone, including competitors, and public disclosure can "
        "affect patent novelty in most jurisdictions. Consider posting to members "
        "only, or to a private community, instead."
    )
