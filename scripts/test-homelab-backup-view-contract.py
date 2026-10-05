#!/usr/bin/env python3
"""Keep the extracted backup view pure and byte-for-byte wrapper compatible."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integrations" / "homelab-readonly"))

import backup_view  # noqa: E402


def bounded_text(value: object, limit: int = 256) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join("".join(char if char.isprintable() else " " for char in value).split())
    return normalized[:limit] or None


def check(report: object, expected: str) -> None:
    result = backup_view.format_backup_status(report, bounded_text)
    assert result == expected, result


check(None, "I couldn't read the Proxmox backup status.")
check(
    {"status": "NOT_CONFIGURED"},
    "Proxmox backup status isn't configured in HADES, so I can't verify Proxmox backup jobs or tasks.",
)
check(
    {"status": "CONFIGURATION_ERROR"},
    "The Proxmox backup read configuration is invalid, so I can't verify backup jobs or tasks.",
)
check(
    {"status": "READABLE", "endpoints": []},
    "I couldn't read any Proxmox backup sources, so backup status is unknown.",
)

empty = {
    "status": "READABLE",
    "retrieved_at": "2026-10-05T12:00:00+00:00",
    "endpoints": [{
        "source_id": "alpha\nsource",
        "status": "HEALTHY",
        "jobs_status": "HEALTHY",
        "tasks_status": "HEALTHY",
        "task_scope": "ALL_GUESTS",
        "jobs": [],
        "tasks": [],
        "unattributed_tasks": [],
    }],
}
empty_expected = (
    "Proxmox alpha source reports no configured vzdump jobs. "
    "No archived vzdump task appears in the bounded recent task history. "
    "This covers Proxmox vzdump records only; it doesn't verify backup contents, "
    "other backup systems, off-site custody, or restoreability. "
    "Source reads completed at 2026-10-05T12:00:00+00:00."
)
check(empty, empty_expected)

partial = {
    "status": "PARTIAL",
    "retrieved_at": "2026-10-05T12:01:00+00:00",
    "endpoints": [{
        "source_id": "beta",
        "status": "PARTIAL",
        "jobs_status": "PARTIAL",
        "tasks_status": "PARTIAL",
        "task_scope": "SELECTED_GUESTS",
        "visible_guest_count": 1,
        "jobs": [{"id": "bounded-job"}],
        "tasks": [{"status": "OK", "guest_id": "102", "finished_at": "2026-10-05T11:59:00+00:00"}],
        "unattributed_tasks": [{"status": "ERROR", "finished_at": "2026-10-05T11:58:00+00:00"}],
    }],
}
partial_result = backup_view.format_backup_status(partial, bounded_text)
assert "1 selected guest(s)" in partial_result
assert "other guest task history is unknown" in partial_result
assert "cannot be attributed to a specific guest" in partial_result
assert "read is partial" in partial_result
assert "doesn't verify backup contents" in partial_result

unavailable = {
    "status": "SOURCE_UNAVAILABLE",
    "retrieved_at": None,
    "endpoints": [{
        "source_id": "gamma",
        "status": "UNAVAILABLE",
        "jobs_status": "UNAVAILABLE",
        "tasks_status": "UNAVAILABLE",
        "task_scope": "UNKNOWN",
        "jobs": [],
        "tasks": [],
        "unattributed_tasks": [],
    }],
}
unavailable_result = backup_view.format_backup_status(unavailable, bounded_text)
assert "backup-job configuration is unavailable" in unavailable_result
assert "Archived vzdump task history is unavailable" in unavailable_result
assert "Source read time is unavailable" in unavailable_result
assert "doesn't verify backup contents" in unavailable_result

print("PASS pure backup formatter preserves unavailable, partial, empty, and task-result semantics")
