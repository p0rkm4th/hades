"""Validate image bytes before they reach the upstream OCR MCP.

The official PaddleOCR MCP also accepts filesystem paths and HTTP(S) URLs.
HADES must call it through an image-data firewall so those broader inputs are
never exposed to a household model.
"""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any


MAX_IMAGE_BYTES = 10 * 1024 * 1024
DATA_URL = re.compile(r"^data:(?P<mime>image/(?:jpeg|png|webp));base64,(?P<data>.+)$", re.I | re.S)
MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ImageInputError(ValueError):
    pass


def _detect_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ImageInputError("image data is not a supported PNG, JPEG, or WebP")


def decode_image_input(value: Any, *, declared_mime: str | None = None) -> dict[str, Any]:
    """Decode only bounded inline image data; reject paths and URLs."""
    if not isinstance(value, str) or not value.strip():
        raise ImageInputError("OCR input must be non-empty inline image data")
    text = value.strip()
    mime = declared_mime.lower().strip() if isinstance(declared_mime, str) else None
    match = DATA_URL.match(text)
    if match:
        if mime and mime != match.group("mime").lower():
            raise ImageInputError("declared MIME does not match the data URL")
        mime = match.group("mime").lower()
        encoded = match.group("data")
    else:
        if "://" in text or text.startswith(("/", "~", "\\")):
            raise ImageInputError("OCR paths and URLs are not accepted")
        encoded = text
    if mime and mime not in MIME_TYPES:
        raise ImageInputError("unsupported OCR image MIME type")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageInputError("OCR input is not valid base64 image data") from exc
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ImageInputError("OCR image is empty or exceeds the 10 MiB limit")
    detected = _detect_mime(data)
    if mime and mime != detected:
        raise ImageInputError("declared MIME does not match image bytes")
    return {"bytes": data, "mime": detected, "size_bytes": len(data)}

