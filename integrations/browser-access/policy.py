"""Profile-selection policy for bounded browser interaction."""

from __future__ import annotations


def select_profile(
    actor_scope: str,
    requested_profile: str = "anonymous",
    *,
    owner_authorized: bool = False,
) -> dict[str, str | bool]:
    """Choose a browser profile from trusted application state.

    The requested profile is treated as a capability request, not proof of
    identity. Owner authorization must come from the authenticated caller and
    server-side policy.
    """
    if not isinstance(actor_scope, str) or not isinstance(requested_profile, str) or not isinstance(owner_authorized, bool):
        return {"allowed": False, "reason": "browser profile authorization input is malformed"}
    if requested_profile == "anonymous":
        return {"allowed": True, "profile": "anonymous"}
    if requested_profile != "owner":
        return {"allowed": False, "reason": "unknown browser profile"}
    if actor_scope != "owner" or owner_authorized is not True:
        return {"allowed": False, "reason": "owner browser profile requires explicit authorization"}
    return {"allowed": True, "profile": "owner"}
