"""Fail-closed authorization contract for a future private Operator proxy."""

from __future__ import annotations

import hmac
import re
from typing import Mapping
from urllib.parse import unquote, urlsplit


def authorize(
    headers: Mapping[str, str],
    *,
    proxy_secret: str,
    owner_groups: tuple[str, ...] = ("hades-owner", "hades-admin"),
) -> dict[str, str | bool]:
    """Accept only identity asserted by a trusted upstream proxy.

    The native Agent Zero listener remains private. This function is not an
    authentication system: the proxy secret authenticates the trusted proxy,
    while the proxy-supplied user/groups determine authorization.
    """
    supplied_secret = headers.get("X-Hades-Proxy-Secret", "")
    if not proxy_secret or not hmac.compare_digest(supplied_secret, proxy_secret):
        return {"allowed": False, "reason": "trusted identity proxy required"}
    user = headers.get("X-Hades-Authenticated-User", "").strip()
    groups = {item.strip() for item in headers.get("X-Hades-Authenticated-Groups", "").split(",") if item.strip()}
    if not user:
        return {"allowed": False, "reason": "authenticated user assertion missing"}
    if not groups.intersection(owner_groups):
        return {"allowed": False, "reason": "Operator requires owner authorization"}
    return {"allowed": True, "user": user}


def validate_path(path: str) -> str:
    """Reject malformed or proxy-escaping paths before upstream forwarding."""
    if not isinstance(path, str) or not path or len(path) > 8192:
        raise ValueError("invalid Operator route path")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in path):
        raise ValueError("invalid Operator route path")
    if "\\" in path or "#" in path or re.search(r"%(?![0-9A-Fa-f]{2})", path):
        raise ValueError("invalid Operator route path")
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/") or parsed.path.startswith("//"):
        raise ValueError("invalid Operator route path")

    # Proxies and upstream routers can decode paths at different layers. Check
    # repeated decoding so encoded and double-encoded dot/separator segments
    # cannot escape a future mounted Operator prefix.
    decoded = parsed.path
    for _ in range(4):
        if decoded.startswith("//") or "\\" in decoded:
            raise ValueError("invalid Operator route path")
        if re.search(r"%(?:2f|5c)", decoded, re.IGNORECASE):
            raise ValueError("invalid Operator route path")
        if any(ord(char) < 0x20 or ord(char) == 0x7F for char in decoded):
            raise ValueError("invalid Operator route path")
        if any(segment in {".", ".."} for segment in decoded.split("/")):
            raise ValueError("invalid Operator route path")
        next_decoded = unquote(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded
    return path
