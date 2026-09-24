"""Fail-closed authorization contract for a future private Operator proxy."""

from __future__ import annotations

import hmac
from typing import Mapping


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
    if not path.startswith("/") or path.startswith("//") or any(char in path for char in "\r\n"):
        raise ValueError("invalid Operator route path")
    return path
