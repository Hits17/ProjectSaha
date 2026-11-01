"""
Upload validation and bounded streaming ingest.

Two problems this closes (security/AUDIT.md SAHA-018, SAHA-031):

1. Content type was taken from the client's multipart header and believed. A
   caller could label anything `application/pdf`. Files uploaded to a vault are
   later handed to a counterparty, so "whatever the uploader claimed" is not an
   acceptable basis for deciding what a file is.

2. `data = await file.read()` pulled the whole body into memory and *then*
   checked the size. On a two-worker box a handful of concurrent 50 MB uploads
   is an out-of-memory condition, and the size limit never got the chance to
   prevent it.

The fix is to read in chunks, abort the moment the cap is exceeded, and identify
the file from its leading bytes. Magic-byte sniffing is not a malware control —
it is a consistency control, and it belongs alongside real scanning (ROADMAP
§2.4), not instead of it.
"""

from dataclasses import dataclass

from fastapi import HTTPException, UploadFile, status

_CHUNK = 64 * 1024


@dataclass(frozen=True)
class Signature:
    label: str
    content_type: str
    prefixes: tuple[bytes, ...]
    offset: int = 0


# Formats a diligence data room legitimately carries. Deliberately conservative:
# an unknown format is rejected rather than passed through, because every file
# here is eventually opened by a counterparty.
_SIGNATURES: tuple[Signature, ...] = (
    Signature("pdf", "application/pdf", (b"%PDF-",)),
    Signature("png", "image/png", (b"\x89PNG\r\n\x1a\n",)),
    Signature("jpeg", "image/jpeg", (b"\xff\xd8\xff",)),
    Signature("gif", "image/gif", (b"GIF87a", b"GIF89a")),
    Signature("webp", "image/webp", (b"WEBP",), offset=8),
    Signature("tiff", "image/tiff", (b"II*\x00", b"MM\x00*")),
    # OOXML (docx/xlsx/pptx) and ODF are ZIP containers; so is a plain .zip.
    Signature("zip", "application/zip", (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")),
    # Legacy Office compound-file binary format (.doc/.xls/.ppt)
    Signature("cfb", "application/x-ole-storage", (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)),
    Signature("rtf", "application/rtf", (b"{\\rtf",)),
    Signature("7z", "application/x-7z-compressed", (b"7z\xbc\xaf\x27\x1c",)),
    Signature("gzip", "application/gzip", (b"\x1f\x8b",)),
)

# Formats whose contents we cannot enumerate cheaply and which expand on open.
# Archive bombs are a real upload vector; until the scanning pipeline in
# ROADMAP §2.4 exists, containers are accepted but flagged for the operator.
_CONTAINER_LABELS = {"zip", "7z", "gzip"}

# Plain text has no magic bytes. Rather than reject it, we verify it decodes as
# UTF-8 and contains no NUL — which is what actually distinguishes text from a
# mislabelled binary.
_TEXT_TYPES = {"text/plain", "text/csv", "text/markdown", "application/json", "application/xml"}


class UploadRejected(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


def _looks_like_text(head: bytes) -> bool:
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        # A multi-byte sequence can legitimately straddle the chunk boundary.
        try:
            head[:-4].decode("utf-8")
        except UnicodeDecodeError:
            return False
    return True


def identify(head: bytes, declared_type: str | None) -> tuple[str, str]:
    """Identify a file from its leading bytes.

    Returns (label, canonical_content_type). Raises UploadRejected when the
    bytes match nothing we accept.
    """
    for sig in _SIGNATURES:
        for prefix in sig.prefixes:
            if head[sig.offset : sig.offset + len(prefix)] == prefix:
                return sig.label, sig.content_type

    declared = (declared_type or "").split(";")[0].strip().lower()
    if declared in _TEXT_TYPES and _looks_like_text(head):
        return "text", declared

    raise UploadRejected(
        "Unrecognised file format. Accepted: PDF, Office documents, images "
        "(PNG/JPEG/GIF/WebP/TIFF), archives, RTF and plain text."
    )


def is_container(label: str) -> bool:
    return label in _CONTAINER_LABELS


async def read_bounded(file: UploadFile, max_bytes: int) -> tuple[bytes, bytes]:
    """Read an upload in chunks, aborting as soon as it exceeds `max_bytes`.

    Returns (head, full_body). `head` is the first chunk, for identification.
    Memory use is bounded by max_bytes, and an oversized upload is rejected
    after ~64 KB rather than after the whole body has been buffered.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise UploadRejected(
                f"File exceeds the {max_bytes // (1024 * 1024)} MB limit",
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        chunks.append(chunk)

    if total == 0:
        raise UploadRejected("Empty file")
    return chunks[0], b"".join(chunks)


_MAX_FILENAME = 255


def safe_filename(raw: str | None) -> str:
    """Normalise a client-supplied filename before it is persisted.

    The download path already sanitises the Content-Disposition header, but the
    stored value is also shown in the UI and included in audit metadata, so it
    is cleaned once at ingest: path components stripped (a filename is never a
    path), control characters removed, length bounded.
    """
    name = (raw or "").replace("\\", "/").split("/")[-1]
    name = "".join(c for c in name if c.isprintable() and c not in '\r\n\t"').strip()
    name = name.lstrip(".") or "upload"
    return name[:_MAX_FILENAME]


async def validate_upload(file: UploadFile, max_bytes: int) -> tuple[bytes, str, str]:
    """Full ingest path: bounded read, then identification from content.

    Returns (data, label, canonical_content_type).
    """
    head, data = await read_bounded(file, max_bytes)
    label, content_type = identify(head, file.content_type)
    return data, label, content_type
