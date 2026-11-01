"""
Deterministic detection of off-platform contact details in negotiation messages.

Why this is not an LLM call any more (security/AUDIT.md SAHA-013): the previous
implementation POSTed the **full plaintext of every negotiation message** to a
third-party inference API in order to answer a yes/no question. Negotiation
content on this platform carries valuation, licensing strategy and trade secrets.
Spending a full confidential disclosure to classify a message is a bad trade at
any accuracy — and the task is rule-expressible, so the accuracy argument does
not hold either.

This runs in-process, needs no network, cannot leak, cannot be prompt-injected,
and returns the same answer every time — which also makes it testable, which the
LLM version was not.

Detection deliberately errs toward catching evasion (`name (at) example dot com`,
digits spelled out, zero-width characters) because that is what someone actually
trying to move a deal off-platform does. False positives are recoverable: the
sender sees why the message was held and can rephrase.
"""

import re
import unicodedata

# Characters used to break up an address so pattern matching misses it.
_INVISIBLE = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD],  # ZWSP, ZWNJ, ZWJ, WJ, BOM, soft hyphen
    None,
)

_SPELLED_DIGITS = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}

# "at"/"dot" obfuscation, in the forms people actually use.
#
# The word forms MUST be anchored on non-letter boundaries. Without that, "at"
# matches inside ordinary words — "WhatsApp" becomes "Wh@sApp" and "patent"
# becomes "p@ent" — which both destroys real detections and invents false ones.
_AT = re.compile(
    r"(?:"
    r"\s*[(\[{]\s*(?:at|@)\s*[)\]}]\s*"      # john (at) example
    r"|\s+at\s+"                              # john at example
    r"|\s*@\s*"                               # john @ example
    r")",
    re.I,
)
_DOT = re.compile(
    r"(?:"
    r"\s*[(\[{]\s*(?:dot|punto|\.)\s*[)\]}]\s*"   # example (dot) com
    r"|\s+(?:dot|punto)\s+"                        # example dot com
    r")",
    re.I,
)

_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

# 7+ digits with common separators — long enough to be a phone number, not a
# quantity, a year, or a patent number (which are matched and excused below).
_PHONE = re.compile(r"(?:\+?\d[\s().-]{0,2}){7,}\d")

_URL = re.compile(
    r"\b(?:https?://|www\.)\S+|\b[A-Z0-9-]+\.(?:com|net|org|io|co|ai|dev|me|app|xyz|biz|info)\b",
    re.I,
)

_HANDLE = re.compile(
    r"\b(?:whatsapp|wa\.me|telegram|t\.me|signal|skype|wechat|line|viber|discord|"
    r"linkedin|calendly|zoom|teams|meet\.google|slack)\b",
    re.I,
)

_SOCIAL_HANDLE = re.compile(r"(?<![A-Z0-9._%+-])@[A-Za-z0-9_]{3,}\b")

# Identifiers that legitimately look like long digit runs in this domain and
# must not trigger a block.
_ALLOWED_NUMERIC = re.compile(
    r"\b(?:US|EP|WO|CA|GB|JP|CN)\s?\d{6,}\s?[A-Z]?\d?\b"     # patent publication numbers
    r"|\b\d{4}-\d{2}-\d{2}\b"                                  # ISO dates
    r"|\bISO\s?\d{3,}\b|\bASTM\s?[A-Z]?\d+\b",                 # standards
    re.I,
)


def _normalise(text: str) -> str:
    """Collapse the obfuscations used to smuggle contact details past a filter."""
    text = unicodedata.normalize("NFKC", text).translate(_INVISIBLE)
    # "j o h n" → "john" only where single letters are space-separated in a run.
    text = re.sub(r"\b(?:[A-Za-z]\s){3,}[A-Za-z]\b", lambda m: m.group(0).replace(" ", ""), text)
    for word, digit in _SPELLED_DIGITS.items():
        text = re.sub(rf"\b{word}\b", digit, text, flags=re.I)
    text = _AT.sub("@", text)
    text = _DOT.sub(".", text)
    return text


def detect(text: str) -> tuple[bool, str | None]:
    """Return (contains_contact, reason). Reason is a short stable slug."""
    if not text or not text.strip():
        return False, None

    normalised = _normalise(text)

    if _EMAIL.search(normalised):
        return True, "email_address"
    if _HANDLE.search(normalised):
        return True, "messaging_platform"
    if _URL.search(normalised):
        return True, "external_url"
    if _SOCIAL_HANDLE.search(normalised):
        return True, "social_handle"

    # Phone last: strip the identifiers that legitimately look numeric first, so
    # a patent number or a standards reference doesn't read as a phone number.
    without_ids = _ALLOWED_NUMERIC.sub(" ", normalised)
    candidate = _PHONE.search(without_ids)
    if candidate and len(re.sub(r"\D", "", candidate.group(0))) >= 7:
        return True, "phone_number"

    return False, None


def contains_contact_info(text: str) -> bool:
    return detect(text)[0]
