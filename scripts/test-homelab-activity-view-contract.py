#!/usr/bin/env python3
"""Keep the extracted recent-activity presenter pure and bounded."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integrations" / "homelab-readonly"))

import activity_view  # noqa: E402


def bounded_text(value: object, limit: int = 256) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join("".join(char if char.isprintable() else " " for char in value).split())
    return normalized[:limit] or None


def render(report: object) -> str:
    return activity_view.format_recent_activity(report, bounded_text)


assert render(None) == "I couldn't read recent homelab activity."
assert render({"status": "READABLE"}) == "I couldn't read recent homelab activity."
assert render({"status": "NOT_CONFIGURED", "endpoints": []}) == (
    "No recent Proxmox or NetBox activity source is configured, so I can't verify recent homelab changes."
)
assert render({"status": "INVALID_REQUEST", "endpoints": []}) == (
    "Choose a recent activity window from 1 to 168 hours."
)
assert render({"status": "SOURCE_UNAVAILABLE", "endpoints": []}) == (
    "I couldn't read the configured Proxmox or NetBox activity sources, so recent homelab changes are unknown."
)

empty = {
    "status": "READABLE", "window_hours": 24,
    "retrieved_at": "2026-10-05T12:00:00+00:00",
    "source_status": {"proxmox": "READABLE", "netbox": "READABLE"},
    "endpoints": [{"events": []}],
    "netbox": {"status": "READABLE", "objects": []},
}
empty_text = render(empty)
assert "In the last 24 hours, no archived Proxmox guest tasks were returned and no recently updated NetBox device/service records were returned." in empty_text
assert "Read at 2026-10-05T12:00:00+00:00." in empty_text
assert "complete homelab change log" in empty_text

partial_without_events = {
    "status": "PARTIAL", "window_hours": 12, "retrieved_at": None,
    "source_status": {"proxmox": "PARTIAL", "netbox": "SOURCE_UNAVAILABLE"},
    "endpoints": [{"events": []}],
    "netbox": {"status": "SOURCE_UNAVAILABLE", "objects": []},
}
partial_text = render(partial_without_events)
assert "no archived guest tasks were returned in the readable Proxmox scope" in partial_text
assert "Proxmox task coverage is partial." in partial_text
assert "NetBox inventory-update coverage is unavailable." in partial_text
assert "Read time unavailable." in partial_text

partial_with_event = {
    "status": "PARTIAL", "retrieved_at": "now\nredacted", "window_hours": 24,
    "source_status": {"proxmox": "READABLE", "netbox": "PARTIAL"},
    "endpoints": [{"events": [{
        "starttime": 2, "guest_id": "102", "node": "node\nalpha",
        "task_type": "qmstart", "status": "OK",
    }]}],
    "netbox": {"status": "PARTIAL", "objects": [{
        "object_type": "device", "name": "box\nbeta", "last_updated": "2026-10-05T11:00:00Z",
    }]},
}
event_text = render(partial_with_event)
assert "qmstart for guest 102 on node alpha (ok)" in event_text
assert "NetBox device box beta was last updated at 2026-10-05T11:00:00Z" in event_text
assert "NetBox inventory-update coverage is partial." in event_text
assert "Read at now redacted." in event_text
assert "node\nalpha" not in event_text and "box\nbeta" not in event_text

many = {
    "status": "READABLE", "source_status": {"proxmox": "READABLE", "netbox": "NOT_CONFIGURED"},
    "endpoints": [{"events": [
        {"starttime": i, "guest_id": str(i), "node": "alpha", "task_type": "qmstart", "status": "OK"}
        for i in range(10)
    ]}],
    "netbox": {"status": "NOT_CONFIGURED", "objects": []},
}
many_text = render(many)
assert "2 additional records were omitted from this summary." in many_text
assert "Read time unavailable." in many_text

print("PASS pure recent-activity formatter handles status, coverage, freshness, bounds, and sanitization")
