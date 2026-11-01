"""
Content safety classification for member-authored posts.

How this differs from services/disclosure.py
--------------------------------------------
The disclosure guard WARNS — it protects an author from harming themselves, and
the author may proceed. This module RESTRICTS — it protects third parties and
the platform, and the author does not get the final say. Different threat model,
different response.

The hard problem, stated plainly
--------------------------------
Saha is an IP and manufacturing marketplace. Legitimate members discuss
energetic materials, pharmaceutical synthesis, agricultural nitrates,
biotechnology and industrial chemistry every day. A keyword blocklist would
delete the product's actual subject matter while barely inconveniencing anyone
determined to misuse it — the worst of both outcomes.

So detection is **intent × subject**, never subject alone:

    a harmful SUBJECT (weapon, toxin, illicit synthesis, …)
      AND an actionable INTENT frame (step-by-step instruction, evasion,
          targeting a person, procurement-for-harm)
      → restrict

    subject without intent  → allow. "Our fertiliser formulation improves
                              nitrogen uptake" is agritech, not bomb-making.
    intent without subject  → allow. "Step-by-step guide to filing a
                              provisional" is a tutorial.

Escalation is asymmetric on purpose: public visibility raises the bar, because
the audience is unbounded and the harm is irreversible.

What this module does NOT do
----------------------------
* It does not contain, encode or reference any actual synthesis route, formulation
  or procedure. It matches structural language patterns only. A moderation
  classifier that embeds a recipe is a liability, not a control.
* It does not decide alone. Everything above the lowest tier reaches a human, and
  every decision is written to the append-only audit log.
* It makes no network call. Same reasoning as contact_detect and disclosure:
  member content does not leave the trust boundary to be classified.
"""

import enum
import re
from dataclasses import dataclass


class SafetyAction(str, enum.Enum):
    ALLOW = "allow"      # nothing detected
    FLAG = "flag"        # published, but queued for review
    HOLD = "hold"        # NOT published; awaits admin approval
    BLOCK = "block"      # refused outright; author cannot publish it anywhere


@dataclass(frozen=True)
class SafetyVerdict:
    action: SafetyAction
    categories: list[str]
    reason: str
    # Shown to the author. Deliberately explains the decision without hinting at
    # what phrasing would have passed.
    author_message: str


# ── Subject matter ───────────────────────────────────────────────────────────
# Presence alone is NOT a finding. These only matter alongside an intent frame.

_SUBJECTS: dict[str, re.Pattern] = {
    "weapons_explosive": re.compile(
        r"\b(?:bomb|explosive|detonat\w*|ied\b|pipe bomb|grenade|landmine"
        r"|blasting cap|shaped charge|car bomb|suicide vest)\b", re.I),
    "weapons_firearm": re.compile(
        r"\b(?:untraceable (?:gun|firearm)|ghost gun|auto ?sear|full[- ]auto conversion"
        r"|3d[- ]printed (?:gun|firearm|receiver)|silencer|suppressor)\b", re.I),
    "chem_bio_weapon": re.compile(
        r"\b(?:nerve agent|chemical weapon|bioweapon|biological weapon|weaponi[sz]ed"
        r"\s+(?:anthrax|pathogen|virus|bacteria)|blister agent|choking agent)\b", re.I),
    "poison": re.compile(
        r"\b(?:poison|toxin|lethal dose|deadly dose|untraceable poison"
        r"|ricin|cyanide pill)\b", re.I),
    "illicit_synthesis": re.compile(
        r"\b(?:methamphetamine|crystal meth|fentanyl|carfentanil|heroin"
        r"|cook(?:ing)? (?:meth|drugs)|drug lab|clandestine lab)\b", re.I),
    "self_harm": re.compile(
        r"\b(?:kill myself|end my life|suicide method|how to die|take my own life"
        r"|painless way to die)\b", re.I),
    "malware": re.compile(
        r"\b(?:ransomware|keylogger|rootkit|botnet|credential stealer"
        r"|remote access trojan|\brat\b payload)\b", re.I),
}

# ── Intent frames ────────────────────────────────────────────────────────────
# Actionable instruction, evasion, targeting, or acquisition-for-harm.

_INSTRUCTION = re.compile(
    r"\b(?:how (?:to|do i|can i) (?:make|build|create|synthesi[sz]e|produce|assemble|obtain)"
    r"|step[- ]by[- ]step|instructions? (?:for|to|on)|recipe for|guide to (?:making|building)"
    r"|tutorial (?:for|on) (?:making|building)|walk me through (?:making|building)"
    r"|what (?:do i|would i) need to (?:make|build))\b", re.I)

_EVASION = re.compile(
    r"\b(?:undetectable|untraceable|avoid detection|evade (?:detection|security|screening)"
    r"|without (?:being )?(?:caught|detected|traced)|bypass (?:security|screening|background check)"
    r"|get (?:it )?(?:past|through) (?:security|customs|screening))\b", re.I)

_TARGETING = re.compile(
    r"\b(?:to (?:kill|murder|hurt|harm|injure|poison) (?:a |my |someone|people|him|her|them)"
    r"|kill (?:a |my |someone|people|him|her|them)"
    r"|hurt (?:someone|people|him|her|them)"
    r"|maximum (?:casualties|damage|body count)|as many people as possible)\b", re.I)

_ACQUISITION = re.compile(
    r"\b(?:where (?:can i|to) (?:buy|get|obtain|source)|no questions asked"
    r"|without a licen[cs]e|without (?:a )?permit|dark ?web|black market)\b", re.I)

# ── Immediate block: no legitimate framing exists ────────────────────────────
# Child sexual abuse material and credible threats of violence. These are not
# moderated, they are refused and escalated.

_ZERO_TOLERANCE = re.compile(
    r"\b(?:child (?:porn|sexual|abuse) (?:material|imagery|content)|csam|cp\b(?= ?(?:trade|swap|share))"
    r"|minor(?:s)? (?:nude|naked|sexual)|underage (?:sexual|nude|porn))\b", re.I)

_CREDIBLE_THREAT = re.compile(
    r"\b(?:i(?:'m| am) going to (?:kill|shoot|bomb|attack)"
    r"|i will (?:kill|shoot|bomb|attack) (?:you|him|her|them|everyone)"
    r"|planning to (?:attack|shoot|bomb))\b", re.I)

# ── Legitimate-context signals ───────────────────────────────────────────────
# The platform's own subject matter. These do not clear a finding on their own,
# but they downgrade an otherwise-ambiguous one from HOLD to FLAG, so a materials
# scientist is reviewed rather than blocked.

_PROFESSIONAL_CONTEXT = re.compile(
    r"\b(?:patent|licen[cs]ing|prior art|uspto|cipo|euipo|wipo"
    r"|regulatory|compliance|iso ?\d|astm|reach|osha|msds|safety data sheet"
    r"|peer[- ]reviewed|publication|journal|doi:|clinical trial"
    r"|manufacturing|supply chain|procurement|quality control"
    r"|detection|remediation|mitigation|defen[cs]e|counter[- ]measure)\b", re.I)

_DEFENSIVE_FRAMING = re.compile(
    r"\b(?:detect(?:ing|ion of)?|screen(?:ing) for|identify(?:ing)?|test(?:ing) for"
    r"|protect(?:ing|ion) (?:against|from)|defen[cd](?:ing|se|ce) against"
    r"|remediat\w+|neutrali[sz]\w+|dispos(?:al|ing) of|cleanup|first aid|antidote"
    r"|regulat(?:ory|ion|ing)|banned|prohibited|illegal)\b", re.I)


_CATEGORY_LABELS = {
    "weapons_explosive": "Explosives or destructive devices",
    "weapons_firearm": "Untraceable or prohibited firearms",
    "chem_bio_weapon": "Chemical or biological weapons",
    "poison": "Poisons or toxins intended to harm",
    "illicit_synthesis": "Illicit drug manufacture",
    "self_harm": "Self-harm",
    "malware": "Malicious software",
    "zero_tolerance": "Child sexual abuse material",
    "credible_threat": "Threat of violence",
}


def _intents(blob: str) -> list[str]:
    found = []
    if _INSTRUCTION.search(blob):
        found.append("instruction")
    if _EVASION.search(blob):
        found.append("evasion")
    if _TARGETING.search(blob):
        found.append("targeting")
    if _ACQUISITION.search(blob):
        found.append("acquisition")
    return found


def classify(text: str, title: str | None = None, visibility: str = "members") -> SafetyVerdict:
    """Classify a draft post.

    `visibility` matters: a public post reaches an unbounded audience and the
    harm is irreversible, so ambiguous content is held rather than flagged.
    """
    blob = f"{title or ''}\n{text or ''}".strip()
    if not blob:
        return SafetyVerdict(SafetyAction.ALLOW, [], "empty", "")

    # ── Zero tolerance ───────────────────────────────────────────────────────
    # No framing makes these acceptable and no review queue should receive them.
    if _ZERO_TOLERANCE.search(blob):
        return SafetyVerdict(
            SafetyAction.BLOCK, ["zero_tolerance"],
            "matched zero-tolerance category",
            "This content cannot be posted. Your account has been referred to the "
            "platform operators.",
        )

    if _CREDIBLE_THREAT.search(blob):
        return SafetyVerdict(
            SafetyAction.BLOCK, ["credible_threat"],
            "matched credible-threat pattern",
            "This reads as a threat of violence and cannot be posted. If this was "
            "not your intent, contact support.",
        )

    # ── Self-harm: support, not punishment ───────────────────────────────────
    # Held rather than blocked, and the author sees a resource rather than a
    # policy citation. Someone in crisis should not be met with an enforcement
    # notice.
    if _SUBJECTS["self_harm"].search(blob):
        return SafetyVerdict(
            SafetyAction.HOLD, ["self_harm"],
            "self-harm language detected",
            "We've held this post. If you're struggling, please talk to someone — "
            "findahelpline.com lists free, confidential support in your country. "
            "A member of our team will review this shortly.",
        )

    # ── Subject × intent ─────────────────────────────────────────────────────
    subjects = [name for name, pattern in _SUBJECTS.items() if pattern.search(blob)]
    intents = _intents(blob)

    if not subjects or not intents:
        # Either alone is ordinary content on this platform. A chemistry post with
        # no instructional frame is chemistry; a how-to with no harmful subject is
        # a tutorial.
        return SafetyVerdict(SafetyAction.ALLOW, [], "no subject/intent pairing", "")

    labels = [_CATEGORY_LABELS.get(s, s) for s in subjects]
    professional = bool(_PROFESSIONAL_CONTEXT.search(blob))
    defensive = bool(_DEFENSIVE_FRAMING.search(blob))

    # Targeting a person, or explicit evasion, is not redeemed by context.
    if "targeting" in intents or "evasion" in intents:
        return SafetyVerdict(
            SafetyAction.BLOCK, subjects,
            f"{', '.join(subjects)} + {', '.join(intents)}",
            "This post appears to describe causing harm to people or evading "
            "safety controls, and cannot be published. If you believe this is a "
            "mistake, contact support — a person will review it.",
        )

    # Instructional or acquisition framing around a harmful subject. Defensive or
    # professional framing downgrades to review rather than clearing it: "how to
    # detect X" is legitimate research, and a human should confirm that.
    if defensive and professional:
        return SafetyVerdict(
            SafetyAction.FLAG, subjects,
            f"{', '.join(subjects)} in a defensive/professional frame",
            "",
        )

    return SafetyVerdict(
        SafetyAction.HOLD, subjects,
        f"{', '.join(subjects)} + {', '.join(intents)}",
        "This post is held for review because it may describe "
        f"{labels[0].lower()}. A moderator will look at it shortly — this usually "
        "takes a few hours. If it's legitimate research or industry discussion, "
        "adding context about your purpose helps.",
    )


def escalate_for_visibility(verdict: SafetyVerdict, visibility: str) -> SafetyVerdict:
    """A public post reaches an unbounded audience, so ambiguity resolves toward
    holding. The same content to members-only — a KYC-verified audience with an
    audit trail — carries materially less risk."""
    if visibility == "public" and verdict.action is SafetyAction.FLAG:
        return SafetyVerdict(
            SafetyAction.HOLD, verdict.categories, verdict.reason + " (escalated: public)",
            "This post is held for review before it goes public. Posting to members "
            "only is available immediately if you'd rather not wait.",
        )
    return verdict


def require_public_text(body: str, title: str | None = None) -> None:
    """Guard new public surfaces that do not yet have a moderation state model.

    Do not claim content is queued when there is no queue for that entity.
    Authors can shorten the public summary or ask moderators for guidance.
    """
    from fastapi import HTTPException
    verdict = escalate_for_visibility(classify(body, title, "public"), "public")
    if verdict.action is not SafetyAction.ALLOW:
        raise HTTPException(status_code=422, detail={"code": "public_content_restricted", "message": "This text cannot be published on this public surface. Use a high-level description or contact a moderator.", "categories": verdict.categories})
