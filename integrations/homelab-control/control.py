"""Bounded, owner-confirmed Proxmox guest control.

This is intentionally a separate write adapter from the read-only homelab
adapter.  It accepts only named operations and approved template aliases; it
does not expose arbitrary API paths, shell, guest execution, or host access.
"""

from __future__ import annotations

import json
import os
import ssl
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen


MAX_RESPONSE_BYTES = 512 * 1024
TIMEOUT_SECONDS = 20
TASK_TIMEOUT_SECONDS = 60
DEFAULT_CORES = 4
DEFAULT_MEMORY_MIB = 8192
MAX_CORES = 16
MAX_MEMORY_MIB = 32768
MAX_DISK_GIB = 500
DEFAULT_VMID_MIN = 900
DEFAULT_VMID_MAX = 19999


def _read_token(path: str) -> str:
    token_path = Path(path)
    if not token_path.is_file() or token_path.is_symlink():
        raise ValueError("control token file must be a regular non-symlink file")
    if token_path.stat().st_mode & 0o777 not in {0o600, 0o640}:
        raise ValueError("control token file must be mode 0600 or 0640")
    token = token_path.read_text(encoding="utf-8").strip()
    if not token or len(token) > 8192 or "\n" in token:
        raise ValueError("control token file is empty or invalid")
    return token


def _base_url() -> str:
    value = os.environ.get("HADES_PROXMOX_CONTROL_URL", "").strip().rstrip("/")
    if not value.endswith("/api2/json"):
        raise ValueError("Proxmox control endpoint is not configured")
    return value


def _approved_nodes() -> set[str]:
    return {v.strip() for v in os.environ.get("HADES_PROXMOX_CONTROL_NODES", "").split(",") if v.strip()}


def _approved_pool() -> str:
    value = os.environ.get("HADES_PROXMOX_CONTROL_POOL", "hades-managed").strip()
    if not value or "/" in value or len(value) > 64:
        raise ValueError("Proxmox control pool is invalid")
    return value


def _template_map() -> dict[str, int]:
    result: dict[str, int] = {}
    for entry in os.environ.get("HADES_PROXMOX_TEMPLATE_MAP", "").split(","):
        if not entry.strip() or ":" not in entry:
            continue
        alias, raw_vmid = entry.split(":", 1)
        try:
            vmid = int(raw_vmid)
        except ValueError:
            continue
        if alias.strip() and vmid > 0:
            result[alias.strip().lower()] = vmid
    return result


def _headers() -> dict[str, str]:
    token_id = os.environ.get("HADES_PROXMOX_CONTROL_TOKEN_ID", "").strip()
    token_file = os.environ.get("HADES_PROXMOX_CONTROL_TOKEN_FILE", "").strip()
    if not token_id or not token_file:
        raise ValueError("Proxmox control credential is not configured")
    return {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"PVEAPIToken={token_id}={_read_token(token_file)}",
    }


def _request(path: str, method: str = "GET", params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{_base_url()}/{path.lstrip('/')}"
    body = None
    if method in {"GET", "DELETE"} and params:
        url = f"{url}?{urlencode(params)}"
    elif params:
        body = urlencode(params).encode("utf-8")
    request = Request(url, headers=_headers(), method=method, data=body)
    ca_file = os.environ.get("HADES_PROXMOX_CONTROL_CA_FILE", "").strip()
    context = ssl.create_default_context(cafile=ca_file) if ca_file else None
    with urlopen(request, timeout=TIMEOUT_SECONDS, context=context) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Proxmox response exceeds bounded size")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Proxmox response must be an object")
    return result


def _vmid_range() -> tuple[int, int]:
    try:
        low = int(os.environ.get("HADES_PROXMOX_CONTROL_VMID_MIN", DEFAULT_VMID_MIN))
        high = int(os.environ.get("HADES_PROXMOX_CONTROL_VMID_MAX", DEFAULT_VMID_MAX))
    except ValueError as exc:
        raise ValueError("Proxmox control VMID range is invalid") from exc
    if not 100 <= low <= high <= 999999999:
        raise ValueError("Proxmox control VMID range is invalid")
    return low, high


def _target(target: dict[str, Any], *, require_vmid: bool) -> tuple[str, int | None]:
    if not isinstance(target, dict):
        raise ValueError("target must be an object")
    allowed = {"node", "vmid"}
    if set(target) - allowed or "node" not in target:
        raise ValueError("target must contain only node and optional vmid")
    node = target["node"]
    if not isinstance(node, str) or node not in _approved_nodes():
        raise ValueError("target node is not approved")
    if "vmid" not in target:
        if require_vmid:
            raise ValueError("target vmid is required for this operation")
        return node, None
    vmid = target["vmid"]
    low, high = _vmid_range()
    if isinstance(vmid, bool) or not isinstance(vmid, int) or not low <= vmid <= high:
        raise ValueError("target vmid is outside the approved self-service range")
    return node, vmid


def _allocate_vmid() -> int:
    low, high = _vmid_range()
    payload = _request("cluster/nextid", params={"vmid": low})
    value = payload.get("data")
    try:
        vmid = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Proxmox did not return a usable self-service VMID") from exc
    if not low <= vmid <= high:
        raise ValueError("no free VMID exists in the approved self-service range")
    return vmid


def _status(node: str, vmid: int) -> str:
    payload = _request(f"nodes/{node}/qemu/{vmid}/status/current")
    status = payload.get("data", {}).get("status")
    if status not in {"running", "stopped"}:
        raise ValueError("Proxmox returned an unsupported guest status")
    return status


def _managed_members() -> set[tuple[str, int]]:
    try:
        payload = _request(f"pools/{_approved_pool()}")
        members = payload.get("data", {}).get("members", [])
    except Exception:
        # Pool.Audit is intentionally not required by the runtime token. Fall
        # back to the narrower VM inventory endpoint; management still
        # requires the explicit HADES-managed tag below.
        payload = _request("cluster/resources", params={"type": "vm"})
        members = payload.get("data", [])
    result = set()
    low, high = _vmid_range()
    for member in members if isinstance(members, list) else []:
        if not isinstance(member, dict) or member.get("type") not in {"qemu", "lxc"}:
            continue
        try:
            vmid = int(member.get("vmid"))
        except (TypeError, ValueError):
            continue
        node = member.get("node")
        if isinstance(node, str) and low <= vmid <= high and node in _approved_nodes():
            result.add((node, vmid))
    return result


def list_managed_guests() -> dict[str, Any]:
    """Return only non-template guests in the approved self-service pool."""
    members = _managed_members()
    guests = []
    for node, vmid in sorted(members):
        try:
            status = _status(node, vmid)
            config = _request(f"nodes/{node}/qemu/{vmid}/config").get("data", {})
            tags = {tag.strip() for tag in str(config.get("tags", "")).split(";") if tag.strip()}
            if config.get("template") or "hades-managed" not in tags:
                continue
            guests.append({
                "node": node,
                "vmid": vmid,
                "name": config.get("name", f"guest-{vmid}"),
                "status": status,
                "hades_managed": True,
            })
        except Exception as exc:
            guests.append({"node": node, "vmid": vmid, "status": "UNKNOWN", "error": str(exc)})
    return {"status": "READY", "guests": guests, "writes_performed": False}


def manage_guest(
    target: dict[str, Any],
    action: str,
    *,
    owner_confirmed: bool = False,
) -> dict[str, Any]:
    """Perform one bounded action on a guest already owned by HADES."""
    try:
        node, vmid = _target(target, require_vmid=True)
        if (node, vmid) not in _managed_members():
            return {"status": "DENIED", "error": "guest is not an HADES-managed self-service workload", "writes_performed": False}
        config = _request(f"nodes/{node}/qemu/{vmid}/config").get("data", {})
        tags = {tag.strip() for tag in str(config.get("tags", "")).split(";") if tag.strip()}
        if "hades-managed" not in tags or config.get("template"):
            return {"status": "DENIED", "error": "guest is not an HADES-managed self-service workload", "writes_performed": False}
    except Exception as exc:
        return {"status": "FAILED", "error": str(exc), "writes_performed": False}
    action = str(action or "").strip().lower()
    if action not in {"status", "start", "stop", "restart", "delete"}:
        return {"status": "FAILED", "error": "action is not approved", "writes_performed": False}
    if action in {"stop", "restart", "delete"} and not owner_confirmed:
        return {"status": "CONFIRMATION_REQUIRED", "action": action, "target": {"node": node, "vmid": vmid}, "writes_performed": False}
    try:
        if action == "status":
            return {"status": "SUCCEEDED", "target": {"node": node, "vmid": vmid}, "observed_status": _status(node, vmid), "writes_performed": False}
        if action == "start":
            if _status(node, vmid) != "running":
                _wait_task(node, _request(f"nodes/{node}/qemu/{vmid}/status/start", "POST").get("data"))
        elif action == "stop":
            if _status(node, vmid) == "running":
                _wait_task(node, _request(f"nodes/{node}/qemu/{vmid}/status/stop", "POST", {"timeout": 30}).get("data"))
        elif action == "restart":
            try:
                _wait_task(node, _request(f"nodes/{node}/qemu/{vmid}/status/reboot", "POST", {"timeout": 15}).get("data"), timeout_seconds=15)
            except Exception:
                # Some approved cloud images expose QGA but do not complete a
                # graceful reboot reliably. The user already confirmed a
                # restart, so use a bounded stop/start fallback and report it
                # distinctly; never claim the graceful reboot succeeded.
                _wait_task(node, _request(f"nodes/{node}/qemu/{vmid}/status/stop", "POST", {"timeout": 30}).get("data"))
                _wait_task(node, _request(f"nodes/{node}/qemu/{vmid}/status/start", "POST").get("data"))
                observed = _status(node, vmid)
                return {"status": "SUCCEEDED", "target": {"node": node, "vmid": vmid}, "action": action, "observed_status": observed, "restart_mode": "bounded-stop-start-fallback", "writes_performed": True, "reconciled": True}
        elif action == "delete":
            if _status(node, vmid) == "running":
                _wait_task(node, _request(f"nodes/{node}/qemu/{vmid}/status/stop", "POST", {"timeout": 30}).get("data"))
            try:
                _wait_task(
                    node,
                    _request(f"nodes/{node}/qemu/{vmid}", "DELETE", {"purge": 1}).get("data"),
                    operation="delete",
                )
            except Exception:
                # A completed destroy can race the task-status endpoint. If
                # authoritative status confirms the guest is gone, report
                # the committed result instead of telling the user deletion
                # failed and inviting a duplicate retry.
                try:
                    _status(node, vmid)
                except HTTPError as verify_error:
                    if verify_error.code == 404:
                        return {
                            "status": "SUCCEEDED",
                            "target": {"node": node, "vmid": vmid},
                            "action": action,
                            "writes_performed": True,
                            "reconciled": True,
                            "reconciliation": "delete-task-complete-guest-absent",
                        }
                    raise
                raise
            return {"status": "SUCCEEDED", "target": {"node": node, "vmid": vmid}, "action": action, "writes_performed": True, "reconciled": True}
        observed = _status(node, vmid)
        return {"status": "SUCCEEDED", "target": {"node": node, "vmid": vmid}, "action": action, "observed_status": observed, "writes_performed": True, "reconciled": True}
    except Exception as exc:
        return {"status": "OUTCOME_UNKNOWN", "target": {"node": node, "vmid": vmid}, "action": action, "error": str(exc), "writes_performed": True, "retry": False}


def _wait_task(
    node: str,
    upid: str,
    timeout_seconds: int = TASK_TIMEOUT_SECONDS,
    operation: str = "Proxmox task",
) -> None:
    if not isinstance(upid, str) or not upid.startswith("UPID:"):
        raise ValueError("Proxmox did not return a valid task identifier")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        payload = _request(f"nodes/{node}/tasks/{upid}/status")
        data = payload.get("data", {})
        if data.get("status") == "stopped":
            if data.get("exitstatus") != "OK":
                raise ValueError(f"Proxmox {operation} did not complete successfully")
            return
        time.sleep(1)
    raise TimeoutError(f"Proxmox {operation} exceeded the bounded wait")


def inspect_templates() -> dict[str, Any]:
    """Return only configured aliases; do not expose arbitrary VM inventory."""
    return {
        "status": "READY" if _template_map() else "UNCONFIGURED",
        "templates": sorted(_template_map()),
        "approved_nodes": sorted(_approved_nodes()),
        "writes_performed": False,
    }


def provision_guest(
    template: str,
    target: dict[str, Any],
    *,
    name: str,
    cores: int = DEFAULT_CORES,
    memory_mib: int = DEFAULT_MEMORY_MIB,
    disk_gib: int = 0,
    owner_confirmed: bool = False,
) -> dict[str, Any]:
    """Clone and start an approved template, then reconcile status.

    The caller must obtain owner authorization and an explicit confirmation in
    the conversation.  This function never accepts a raw template VMID or API
    path from model text.
    """
    alias = str(template or "").strip().lower()
    template_vmid = _template_map().get(alias)
    if not template_vmid:
        return {"status": "FAILED", "error": "server template is not approved", "writes_performed": False}
    try:
        node, vmid = _target(target, require_vmid=False)
    except ValueError as exc:
        return {"status": "FAILED", "error": str(exc), "writes_performed": False}
    if not owner_confirmed:
        preview_target = {"node": node}
        if vmid is not None:
            preview_target["vmid"] = vmid
        return {
            "status": "CONFIRMATION_REQUIRED",
            "operation": "provision_guest",
            "template": alias,
            "target": preview_target,
            "name": name,
            "cores": cores,
            "memory_mib": memory_mib,
            "disk_gib": disk_gib,
            "writes_performed": False,
        }
    if not isinstance(name, str) or not name.strip() or len(name) > 64:
        return {"status": "FAILED", "error": "guest name is invalid", "writes_performed": False}
    if isinstance(cores, bool) or not isinstance(cores, int) or not 1 <= cores <= MAX_CORES:
        return {"status": "FAILED", "error": "cores exceed the approved limit", "writes_performed": False}
    if isinstance(memory_mib, bool) or not isinstance(memory_mib, int) or not 512 <= memory_mib <= MAX_MEMORY_MIB:
        return {"status": "FAILED", "error": "memory exceeds the approved limit", "writes_performed": False}
    if isinstance(disk_gib, bool) or not isinstance(disk_gib, int) or not 0 <= disk_gib <= MAX_DISK_GIB:
        return {"status": "FAILED", "error": "disk exceeds the approved limit", "writes_performed": False}
    try:
        if vmid is None:
            vmid = _allocate_vmid()
        clone_result = _request(
            f"nodes/{node}/qemu/{template_vmid}/clone",
            "POST",
            {
                "newid": vmid,
                "target": node,
                "pool": _approved_pool(),
                "full": 1,
                "name": name.strip(),
            },
        )
        _wait_task(node, clone_result.get("data"))
        _request(
            f"nodes/{node}/qemu/{vmid}/config",
            "PUT",
            {"cores": cores, "memory": memory_mib, "onboot": 1, "tags": "hades-managed"},
        )
        if disk_gib:
            _request(f"nodes/{node}/qemu/{vmid}/resize", "PUT", {"disk": "scsi0", "size": f"+{disk_gib}G"})
        start_result = _request(f"nodes/{node}/qemu/{vmid}/status/start", "POST")
        _wait_task(node, start_result.get("data"))
        observed = _status(node, vmid)
    except Exception as exc:
        return {"status": "OUTCOME_UNKNOWN", "error": str(exc), "target": {"node": node, "vmid": vmid}, "writes_performed": True, "retry": False}
    if observed != "running":
        return {"status": "FAILED", "error": f"guest read-back is {observed}", "target": {"node": node, "vmid": vmid}, "writes_performed": True}
    return {"status": "SUCCEEDED", "target": {"node": node, "vmid": vmid}, "template": alias, "observed_status": observed, "writes_performed": True, "reconciled": True}
