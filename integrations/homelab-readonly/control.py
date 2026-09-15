"""Preview and reconcile narrowly bounded homelab control operations.

This module deliberately has no transport or executor. It prepares a
Proxmox-shaped request only after exact-target, canonical-precondition,
owner-authorization, and confirmation checks. A future private executor must
perform the operation and read Proxmox back before reporting an outcome.
"""

from __future__ import annotations

from typing import Any


OPERATIONS = {
    "start_guest": {"before": "stopped", "after": "running"},
    "stop_guest": {"before": "running", "after": "stopped"},
    "restart_guest": {"before": "running", "after": "running"},
}


def build_control_preview(
    operation: str,
    target: dict[str, Any],
    canonical_runtime: dict[str, Any],
    *,
    owner_authorized: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Build a write-free, exact-target Proxmox control request."""
    spec = OPERATIONS.get(operation)
    if spec is None:
        return {"status": "FAILED", "error": "operation is not an approved bounded guest operation"}
    if not isinstance(target, dict) or set(target) != {"node", "vmid"}:
        return {"status": "FAILED", "error": "target must contain exactly node and vmid"}
    if not isinstance(target["node"], str) or not target["node"].strip():
        return {"status": "FAILED", "error": "target node is required"}
    if isinstance(target["vmid"], bool) or not isinstance(target["vmid"], int) or target["vmid"] < 1:
        return {"status": "FAILED", "error": "target vmid must be a positive integer"}
    if not isinstance(canonical_runtime, dict):
        return {"status": "FAILED", "error": "canonical Proxmox runtime is required"}
    if canonical_runtime.get("node") != target["node"] or canonical_runtime.get("vmid") != target["vmid"]:
        return {"status": "FAILED", "error": "canonical runtime does not match the exact target"}
    if canonical_runtime.get("status") != spec["before"]:
        return {"status": "FAILED", "error": f"canonical guest must be {spec['before']} before {operation}"}
    preview = {
        "status": "PREVIEW",
        "operation": operation,
        "target": {"node": target["node"], "vmid": target["vmid"]},
        "canonical_source": "Proxmox",
        "expected_status_after": spec["after"],
        "requires_owner_authorization": True,
        "requires_confirmation": True,
        "writes_performed": False,
        "reconcile_after_write": True,
        "reconcile_before_retry": True,
    }
    if not owner_authorized:
        preview["status"] = "OWNER_GATED"
        return preview
    if not confirm:
        return preview
    preview["status"] = "READY_TO_EXECUTE"
    return preview


def reconcile_control_outcome(
    plan: dict[str, Any],
    observed_runtime: dict[str, Any] | None,
    *,
    transport_outcome: str,
) -> dict[str, Any]:
    """Classify a control result from transport and canonical read-back."""
    if plan.get("status") != "READY_TO_EXECUTE":
        return {"status": "FAILED", "error": "only a ready plan can be reconciled"}
    if transport_outcome not in {"SUCCEEDED", "FAILED", "UNKNOWN"}:
        return {"status": "FAILED", "error": "invalid transport outcome"}
    target = plan["target"]
    expected = plan["expected_status_after"]
    matches = isinstance(observed_runtime, dict) and all(
        observed_runtime.get(key) == value for key, value in (
            ("node", target["node"]), ("vmid", target["vmid"]), ("status", expected)
        )
    )
    if matches:
        return {"status": "SUCCEEDED", "canonical_source": "Proxmox", "reconciled": True}
    if transport_outcome == "FAILED" and isinstance(observed_runtime, dict):
        return {"status": "FAILED", "canonical_source": "Proxmox", "reconciled": True}
    return {"status": "OUTCOME UNKNOWN", "canonical_source": "Proxmox", "reconciled": False, "retry": False}
