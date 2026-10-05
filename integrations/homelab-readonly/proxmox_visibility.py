"""Pure Proxmox effective-permission policy for guest visibility.

This module classifies permission payloads only. Fetching, freshness, and
failure-to-UNKNOWN behavior belong to the server adapter.
"""

from __future__ import annotations

import re


def permission_enabled(value: object) -> bool:
    if value is False or (type(value) is int and value == 0) or value == "0":
        return False
    if value is True or (type(value) is int and value > 0) or value == "1":
        return True
    raise ValueError("Proxmox effective-permissions privilege has an invalid value")


def _permission_rows(payload: dict) -> dict:
    permissions = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(permissions, dict):
        raise ValueError("Proxmox effective-permissions response has an invalid shape")
    for path, grants in permissions.items():
        if not isinstance(path, str) or not path.startswith("/") or not isinstance(grants, dict):
            raise ValueError("Proxmox effective-permissions row has an invalid shape")
        for privilege in ("VM.Audit", "NoAccess"):
            if privilege in grants:
                permission_enabled(grants[privilege])
    return permissions


def guest_visibility(payload: dict) -> dict:
    """State whether effective read ACLs cover all or only selected guests."""
    permissions = _permission_rows(payload)
    broad = False
    selected: set[str] = set()
    excluded = False
    for path, grants in permissions.items():
        if not isinstance(path, str) or not isinstance(grants, dict):
            continue
        if path in {"/", "/vms"} or path.startswith("/vms/"):
            excluded = excluded or permission_enabled(grants.get("NoAccess", 0))
        if not permission_enabled(grants.get("VM.Audit", 0)):
            continue
        if path in {"/", "/vms"}:
            broad = True
        elif path.startswith(("/vms/", "/pool/")):
            selected.add(path)
    if broad and not excluded:
        return {"status": "COMPLETE", "scope": "ALL_GUESTS", "scoped_guest_count": None}
    if broad and excluded:
        return {"status": "PARTIAL", "scope": "ALL_GUESTS_WITH_EXCLUSIONS",
                "scoped_guest_count": None}
    if selected:
        vm_paths = [path for path in selected if re.fullmatch(r"/vms/[1-9][0-9]{0,19}", path)]
        count = len(vm_paths) if len(vm_paths) == len(selected) else None
        return {"status": "PARTIAL", "scope": "SELECTED_GUESTS", "scoped_guest_count": count}
    return {"status": "PARTIAL", "scope": "NO_GUEST_AUDIT", "scoped_guest_count": 0}


def aggregate_guest_visibility(rows: list[dict]) -> dict:
    states = [row.get("status", "UNKNOWN") for row in rows]
    scopes = {row.get("scope", "UNKNOWN") for row in rows}
    status = ("NOT_CONFIGURED" if not rows else "COMPLETE" if all(s == "COMPLETE" for s in states)
              else "PARTIAL" if any(s == "PARTIAL" for s in states) else "UNKNOWN")
    scope = next(iter(scopes)) if len(scopes) == 1 else "MIXED" if scopes else "UNKNOWN"
    return {"status": status, "scope": scope}


def guest_task_scope(payload: dict) -> dict:
    """Return the subset of guest IDs safe to include from a task listing."""
    permissions = _permission_rows(payload)
    broad = False
    denied: set[str] = set()
    explicit: set[str] = set()
    has_non_enumerable_scope = False
    has_non_enumerable_exclusion = False
    for path, grants in permissions.items():
        if not isinstance(path, str) or not isinstance(grants, dict):
            continue
        vm_match = re.fullmatch(r"/vms/([1-9][0-9]{0,19})", path)
        if vm_match and permission_enabled(grants.get("NoAccess", 0)):
            denied.add(vm_match.group(1))
        elif permission_enabled(grants.get("NoAccess", 0)) and (
            path in {"/", "/vms"} or path.startswith(("/vms/", "/pool/"))
        ):
            has_non_enumerable_exclusion = True
        if not permission_enabled(grants.get("VM.Audit", 0)):
            continue
        if path in {"/", "/vms"}:
            broad = True
        elif vm_match:
            explicit.add(vm_match.group(1))
        elif path.startswith(("/vms/", "/pool/")):
            has_non_enumerable_scope = True
    if broad and not has_non_enumerable_exclusion:
        return {
            "scope": "PARTIAL" if denied or has_non_enumerable_scope else "ALL_GUESTS",
            "all_guests": True,
            "guest_ids": [],
            "excluded_guest_ids": sorted(denied),
        }
    allowed_explicit = sorted(explicit - denied)
    return {
        "scope": "PARTIAL" if broad or has_non_enumerable_scope or has_non_enumerable_exclusion else (
            "SELECTED_GUESTS" if allowed_explicit else "NO_GUEST_AUDIT"
        ),
        "all_guests": False,
        "guest_ids": allowed_explicit,
        "excluded_guest_ids": sorted(denied),
    }
