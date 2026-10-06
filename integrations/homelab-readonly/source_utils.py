"""Small bounded helpers shared by read-only homelab source adapters."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError


def bounded_text(value: object, limit: int = 256) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join("".join(char if char.isprintable() else " " for char in value).split())
    return normalized[:limit] or None


def source_error_code(exc: BaseException) -> str:
    """Return useful failure classes without exposing exception text or URLs."""
    if isinstance(exc, HTTPError):
        return f"HTTP_{exc.code}"
    if isinstance(exc, URLError) and isinstance(exc.reason, TimeoutError):
        return "TIMEOUT"
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    if isinstance(exc, URLError):
        return "SOURCE_UNREACHABLE"
    if isinstance(exc, json.JSONDecodeError):
        return "INVALID_JSON"
    if isinstance(exc, ValueError):
        return "INVALID_RESPONSE_OR_CONFIGURATION"
    if isinstance(exc, OSError):
        return "SOURCE_IO_ERROR"
    return "SOURCE_ERROR"


def retrieved_at() -> str:
    return datetime.now(timezone.utc).isoformat()
