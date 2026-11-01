"""
Regression suites for SAHA-018/031 (upload validation) and SAHA-017/026/030
(token handling and MFA replay).

Uploads: content type came from the client's multipart header and was believed,
and the size check ran *after* `await file.read()` had already buffered the whole
body. Vault files are handed to a counterparty later, so "whatever the uploader
claimed" was never an acceptable basis for deciding what a file is.

Tokens: python-jose (unmaintained since 2021) was the JWT implementation for the
whole auth system; the SSE stream accepted a full access token as a query
parameter, which put live credentials into nginx access logs; and TOTP codes had
no replay guard, so an intercepted code stayed usable for up to 90 seconds.
"""

from contextlib import contextmanager
from tempfile import SpooledTemporaryFile

import pytest
from fastapi import HTTPException, UploadFile

from app.services import uploads

PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
ZIP = b"PK\x03\x04" + b"\x00" * 32
DOCX = b"PK\x03\x04" + b"word/document.xml" + b"\x00" * 16


@contextmanager
def _upload(data: bytes, filename="f.bin", content_type="application/octet-stream"):
    # Match Starlette's multipart upload representation. Bare BytesIO lacks
    # the spool state, so UploadFile treats it as disk-backed and dispatches
    # reads to a thread pool even though these are in-memory unit tests.
    with SpooledTemporaryFile(max_size=len(data) + 1) as stream:
        stream.write(data)
        stream.seek(0)
        yield UploadFile(file=stream, filename=filename,
                         headers={"content-type": content_type})


# ── Identification comes from the bytes, not the header ─────────────────────

def test_identifies_pdf_regardless_of_declared_type():
    label, ctype = uploads.identify(PDF, "image/png")
    assert label == "pdf" and ctype == "application/pdf"


def test_png_declared_as_pdf_is_identified_as_png():
    label, _ = uploads.identify(PNG, "application/pdf")
    assert label == "png"


def test_executable_labelled_as_pdf_is_rejected():
    """The mismatch that matters: arbitrary content wearing a document label."""
    with pytest.raises(HTTPException) as exc:
        uploads.identify(b"MZ\x90\x00\x03", "application/pdf")
    assert exc.value.status_code == 400


def test_office_documents_are_recognised_as_containers():
    label, _ = uploads.identify(DOCX, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert label == "zip" and uploads.is_container(label)


def test_plain_text_is_accepted_when_it_really_is_text():
    label, ctype = uploads.identify(b"claim 1: a widget comprising...", "text/plain")
    assert label == "text" and ctype == "text/plain"


def test_binary_declared_as_text_is_rejected():
    with pytest.raises(HTTPException):
        uploads.identify(b"\x00\x01\x02\xff\xfe", "text/plain")


# ── Bounded reads ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_oversized_upload_is_rejected():
    with _upload(b"x" * 5000) as file, pytest.raises(HTTPException) as exc:
        await uploads.read_bounded(file, max_bytes=1000)
    assert exc.value.status_code == 413


@pytest.mark.anyio
async def test_oversized_upload_aborts_without_buffering_everything():
    """The point of the streaming read: memory use is bounded by the cap, not by
    what the caller chose to send."""
    huge = b"x" * (4 * 1024 * 1024)
    with _upload(huge) as file:
        with pytest.raises(HTTPException):
            await uploads.read_bounded(file, max_bytes=64 * 1024)
        assert file.file.tell() <= 2 * 64 * 1024
        assert file.file.tell() < len(huge)


@pytest.mark.anyio
async def test_empty_upload_is_rejected():
    with _upload(b"") as file, pytest.raises(HTTPException) as exc:
        await uploads.read_bounded(file, max_bytes=1000)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_valid_upload_returns_head_and_body():
    with _upload(PDF) as file:
        head, data = await uploads.read_bounded(file, max_bytes=1_000_000)
    assert data == PDF and head.startswith(b"%PDF")


# ── Filename normalisation ──────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected_not_in", [
    ("../../etc/passwd", "/"),
    ("..\\..\\windows\\system32", "\\"),
    ('bad"name.pdf', '"'),
    ("with\r\nnewline.pdf", "\n"),
])
def test_filename_is_normalised(raw, expected_not_in):
    assert expected_not_in not in uploads.safe_filename(raw)


def test_filename_keeps_something_usable():
    assert uploads.safe_filename("../../claims-draft.pdf") == "claims-draft.pdf"
    assert uploads.safe_filename(None) == "upload"
    assert uploads.safe_filename("...") == "upload"


def test_filename_length_is_bounded():
    assert len(uploads.safe_filename("a" * 5000)) <= 255


def test_storage_key_does_not_embed_the_filename():
    """Object keys are opaque UUID paths. A filename can contain separators and
    unicode lookalikes, and the object store is not the place to discover that."""
    import inspect
    from app.services import vault

    source = inspect.getsource(vault.store_encrypted_file)
    assert 'f"vault/{listing_id}/{asset_id}.enc"' in source


# ── Tokens (SAHA-026, SAHA-017) ─────────────────────────────────────────────

def test_token_type_confusion_is_rejected():
    """An email-verification token must not be presentable as an access token."""
    import uuid
    from app.core.security import create_email_verify_token, decode_access_token

    token = create_email_verify_token(str(uuid.uuid4()), "member@example.invalid")
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token)
    assert exc.value.status_code == 401


def test_sse_ticket_is_not_an_access_token():
    import uuid
    from app.core.security import create_sse_ticket, decode_access_token

    with pytest.raises(HTTPException):
        decode_access_token(create_sse_ticket(str(uuid.uuid4())))


def test_access_token_is_not_an_sse_ticket():
    import uuid
    from app.core.security import create_access_token, decode_sse_ticket

    with pytest.raises(HTTPException):
        decode_sse_ticket(create_access_token(str(uuid.uuid4()), "creator"))


def test_algorithm_none_is_rejected():
    """Classic JWT confusion: an unsigned token must never be accepted."""
    import base64, json, uuid
    from app.core.security import decode_access_token

    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": str(uuid.uuid4()), "type": "access", "exp": 9999999999}).encode()
    ).rstrip(b"=")
    with pytest.raises(HTTPException):
        decode_access_token(f"{header.decode()}.{payload.decode()}.")


def test_token_signed_with_another_key_is_rejected():
    import uuid
    import jwt as pyjwt
    from app.core.security import decode_access_token

    forged = pyjwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access", "exp": 9999999999,
         "iss": "saha", "aud": "saha-api", "iat": 1},
        "attacker-key", algorithm="HS256",
    )
    with pytest.raises(HTTPException):
        decode_access_token(forged)


def test_issuer_and_audience_are_asserted():
    import uuid
    from app.core.config import settings
    import jwt as pyjwt
    from app.core.security import decode_access_token

    wrong_aud = pyjwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access", "exp": 9999999999,
         "iss": "saha", "aud": "someone-else", "iat": 1},
        settings.SECRET_KEY, algorithm="HS256",
    )
    with pytest.raises(HTTPException):
        decode_access_token(wrong_aud)


def test_every_token_carries_a_jti():
    """Gives us a handle for revocation and for correlating a token to audit
    events."""
    import uuid
    from app.core.security import create_access_token
    from app.core.tokens import decode_token

    payload = decode_token(create_access_token(str(uuid.uuid4()), "creator"), "access")
    assert payload.get("jti")


# ── TOTP replay (SAHA-030) ──────────────────────────────────────────────────

def test_totp_code_cannot_be_replayed():
    import time
    from app.core import mfa

    secret = mfa.generate_secret()
    counter = int(time.time() // 30)
    code = mfa._hotp(secret, counter)

    ok, matched = mfa.verify_with_counter(secret, code)
    assert ok and matched == counter

    replay_ok, _ = mfa.verify_with_counter(secret, code, last_counter=matched)
    assert not replay_ok, "an intercepted code must not be reusable within its window"


def test_totp_still_accepts_the_next_period():
    import time
    from app.core import mfa

    secret = mfa.generate_secret()
    counter = int(time.time() // 30)
    ok, _ = mfa.verify_with_counter(secret, mfa._hotp(secret, counter + 1), last_counter=counter)
    assert ok


def test_totp_rejects_garbage():
    from app.core import mfa

    secret = mfa.generate_secret()
    for bad in ("", "abcdef", "12345", None):
        assert mfa.verify_with_counter(secret, bad)[0] is False
