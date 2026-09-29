"""Decoding and validating an image sent as a `data:` URL (the web portal's ticket attachments)."""
import base64
import re
from dataclasses import dataclass

# Matches the frontend's own constants (frontend/src/app/api/attachments - the route this replaces).
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024  # 5 MB, decoded
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}

_DATA_URL_RE = re.compile(r"^data:([^;]+);base64,(.*)$", re.DOTALL)


class InvalidAttachment(ValueError):
    """The `data:` URL is malformed, an unsupported type, or too large."""


@dataclass
class DecodedAttachment:
    content: bytes
    mime_type: str


def decode_data_url(data_url: str) -> DecodedAttachment:
    """
    Decodes and validates a `data:<mime>;base64,<data>` URL.

    Raises `InvalidAttachment` for a malformed URL, a MIME type outside `ALLOWED_MIME_TYPES`, invalid
    base64, or decoded content over `MAX_ATTACHMENT_BYTES`. Never trusts the declared size: the limit
    is enforced on the bytes actually decoded.
    """
    match = _DATA_URL_RE.match(data_url.strip())
    if not match:
        raise InvalidAttachment("Not a data: URL (expected data:<mime>;base64,<data>).")

    mime_type = match.group(1).strip().lower()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise InvalidAttachment(f"Unsupported image type '{mime_type}'.")

    try:
        content = base64.b64decode(match.group(2), validate=True)
    except Exception as exc:
        raise InvalidAttachment("Invalid base64 content.") from exc

    if not content:
        raise InvalidAttachment("Empty attachment.")
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise InvalidAttachment(f"Attachment exceeds {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB.")

    return DecodedAttachment(content=content, mime_type=mime_type)


def extension_for(mime_type: str) -> str:
    """File extension Telegram/clients should see for `mime_type` (falls back to 'png')."""
    return {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
    }.get(mime_type, "png")
