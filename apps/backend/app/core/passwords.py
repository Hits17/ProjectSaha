"""Central password policy so the API and any future callers agree on the rules."""

from app.core.config import settings

# A tiny denylist of the most-abused passwords. Not a substitute for length,
# but cheaply blocks the worst credential-stuffing seeds.
_COMMON = {
    "password", "password123", "123456789012", "qwertyuiop12",
    "administrator", "changeme1234", "letmein12345", "welcome12345",
}


def validate_password(pw: str) -> str:
    """Raise ValueError on policy violation; return the password unchanged on success."""
    if len(pw) < settings.PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters")
    if len(pw.encode("utf-8")) > 72:
        # bcrypt silently truncates beyond 72 bytes — reject instead.
        raise ValueError("Password must be at most 72 bytes")
    if pw.lower() in _COMMON:
        raise ValueError("Password is too common — choose something less guessable")
    has_letter = any(c.isalpha() for c in pw)
    has_number = any(c.isdigit() for c in pw)
    if not (has_letter and has_number):
        raise ValueError("Password must contain both letters and numbers")
    return pw
