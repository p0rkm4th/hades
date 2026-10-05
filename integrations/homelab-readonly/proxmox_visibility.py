"""Pure effective-permission policy for Proxmox guest visibility."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit


def permissions_url(resources_url: str) -> str:
    """Resolve effective permissions for a configured cluster/resources URL."""
    parsed = urlsplit(resources_url)
    suffix = "/cluster/resources"
    path = parsed.path.rstrip("/")
    if not path.endswith(suffix):
        raise ValueError("Proxmox resource URL has no recognized API path")
    return urlunsplit((parsed.scheme, parsed.netloc,
                       path[:-len(suffix)] + "/access/permissions", "", ""))


def _permission_enabled(value: object) -> bool:
    return value is True or (type(value) is int and value > 0) or value == "1"


def guest_visibility(payload: dict) -> dict:
    """Classify the effective VM.Audit coverage represented by Proxmox rows."""
    permissions = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(permissions, dict):
        raise ValueError("Proxmox effective-permissions response has an invalid shape")
    broad = False
    selected: set[str] = set()
    excluded = False
    for path, grants in permissions.items():
        if not isinstance(path, str) or not isinstance(grants, dict):
            continue
        if path in {"/", "/vms"} or path.startswith("/vms/"):
            excluded = excluded or _permission_enabled(grants.get("NoAccess"))
        if not _permission_enabled(grants.get("VM.Audit")):
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
    """Aggregate endpoint scopes without treating UNKNOWN as successful coverage."""
    states = [row.get("status", "UNKNOWN") for row in rows]
    scopes = {row.get("scope", "UNKNOWN") for row in rows}
    status = ("NOT_CONFIGURED" if not rows else "COMPLETE" if all(s == "COMPLETE" for s in states)
              else "PARTIAL" if any(s == "PARTIAL" for s in states) else "UNKNOWN")
    scope = next(iter(scopes)) if len(scopes) == 1 else "MIXED" if scopes else "UNKNOWN"
    return {"status": status, "scope": scope}
