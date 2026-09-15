"""Policy and response shaping for the read-only Home Assistant adapter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

SENSITIVE_MARKERS = (
    "lock.",
    "cover.garage",
    "alarm_control_panel.",
    "camera.",
    "door_access.",
)


def is_sensitive_entity(entity_id: str) -> bool:
    normalized = str(entity_id).casefold()
    return any(normalized.startswith(marker) for marker in SENSITIVE_MARKERS)


def validate_allowlist(entity_ids: list[str]) -> list[str]:
    selected: list[str] = []
    for entity_id in entity_ids:
        value = str(entity_id).strip()
        if not value or " " in value or "." not in value:
            raise ValueError("entity allowlist contains an invalid entity ID")
        if is_sensitive_entity(value):
            raise ValueError("security-sensitive Home Assistant entity is excluded")
        if value not in selected:
            selected.append(value)
    if not selected:
        raise ValueError("Home Assistant entity allowlist is empty")
    return selected


def shape_state(state: dict[str, Any], *, now: datetime | None = None, max_age: timedelta = timedelta(minutes=5)) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    raw_updated = state.get("last_updated")
    freshness = "UNKNOWN"
    try:
        observed = datetime.fromisoformat(str(raw_updated).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        freshness = "UNKNOWN" if observed > now else ("FRESH" if now - observed <= max_age else "STALE")
    except (TypeError, ValueError):
        pass
    return {
        "entity_id": state.get("entity_id"),
        "state": state.get("state"),
        "attributes": state.get("attributes", {}),
        "last_updated": raw_updated,
        "freshness": freshness,
        "source": "Home Assistant",
    }
