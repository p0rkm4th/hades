"""Read-only MCP composition adapter for approved homelab endpoints."""

from __future__ import annotations

import json
import os
import re
import ssl
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import anyio
import yaml
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from inference_view import (
    _format_node_activity_fallback,
    _inference_monitor_is_linked_to_target,
    _inference_resource_names,
    format_gpu_hardware_target_response,
    format_inference_inventory_response,
    resolve_inference_node_target,
)
from reconcile import summarize
from backup_view import format_homelab_backup_status as _format_homelab_backup_status
from catalog import propose_inventory_candidates
from scan import DEFAULT_PORTS, run_bounded_scan
from config import (
    homelab_identity_links_file,
    netbox_services_spec,
    proxmox_specs,
    proxmox_source_ids,
    proxmox_token_ids,
    supporting_source_specs,
    gpu_telemetry_config_file,
    inference_endpoint_specs,
)
from gpu_telemetry import read_gpu_telemetry


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TOKEN_BYTES = 8192
MAX_IDENTITY_LINK_BYTES = 256 * 1024
TIMEOUT_SECONDS = 10
TOOLS = [Tool(
    name="homelab_recent_activity",
    description=(
        "Owner-only bounded read of recent Proxmox guest tasks and NetBox "
        "device/service update timestamps. Reports effective VM.Audit scope, "
        "source freshness, partial coverage, and limitations; not a complete "
        "change log and performs no writes."
    ),
    inputSchema={"type": "object", "properties": {
        "window_hours": {"type": "integer", "minimum": 1, "maximum": 168},
    }},
), Tool(
    name="homelab_backup_status",
    description=(
        "Owner-only read of configured Proxmox vzdump schedules and bounded "
        "archived task history filtered by effective VM.Audit visibility. "
        "Reports source scope and freshness; does not verify artifacts, "
        "off-site custody, storage health, or restoreability. Read-only."
    ),
    inputSchema={"type": "object", "properties": {}},
), Tool(
    name="homelab_summary",
    description=(
        "MANDATORY for any owner question about servers, hosts, VMs, online "
        "status, application-service endpoints, ports, or homelab infrastructure: "
        "call this tool first. Read approved Proxmox runtime and effective "
        "guest-audit visibility, NetBox intended device and application-service "
        "inventory, and Uptime Kuma observed availability, plus clearly labeled supplemental "
        "hardware inventory. Only Proxmox runtime_status=online for "
        "hosts or running for guests means currently live; NetBox-only "
        "inventory is not liveness. Explain "
        "guest-scope completeness separately from visible rows, explain "
        "conflicts and stale observations; never perform writes or execute "
        "network commands."
    ),
    inputSchema={"type": "object", "properties": {}},
), Tool(
    name="homelab_owner_snapshot",
    description=(
        "For compound owner questions about current homelab status and "
        "hardware, read the live Proxmox/NetBox/Uptime Kuma summary together "
        "with the observed compute capability matrix. Proxmox remains the "
        "only liveness authority; hardware inventory never implies online "
        "status. This is read-only and performs no writes."
    ),
    inputSchema={"type": "object", "properties": {}},
), Tool(
    name="homelab_discovery_scan",
    description=(
        "Run a bounded read-only TCP discovery scan inside the explicitly "
        "configured HADES_DISCOVERY_ALLOWED_NETWORKS allowlist. Return "
        "normalized transient evidence only; never write inventory or run "
        "arbitrary commands."
    ),
    inputSchema={"type": "object", "properties": {
        "target": {"type": "string", "description": "CIDR inside the configured allowlist"},
        "ports": {"type": "string", "description": "Optional comma-separated TCP ports"},
    }, "required": ["target"]},
), Tool(
    name="homelab_compute_capabilities",
    description=(
        "Read the tracked observed hardware capability matrix for the current "
        "homelab. Report confirmed GPU/CPU/RAM inventory separately from "
        "current runtime or CUDA availability; this is read-only and never "
        "authorizes workload placement or host control."
    ),
    inputSchema={"type": "object", "properties": {}},
), Tool(
    name="homelab_inference_capacity",
    description=(
        "Owner-only composition for current inference/GPU capacity questions. "
        "Reads Proxmox/NetBox/availability summary, observed hardware inventory, "
        "provider model/residency catalogs, and fixed-command live GPU telemetry. "
        "Keeps each source separate; does not estimate fit or authorize placement."
    ),
    inputSchema={"type": "object", "properties": {}},
), Tool(
    name="homelab_inference_inventory",
    description=(
        "Owner-only read of configured provider model catalogs and, for Ollama, "
        "loaded-model state. Catalog/residency reads do not prove generation, "
        "GPU availability, or model fit. No provider writes are performed."
    ),
    inputSchema={"type": "object", "properties": {}},
), Tool(
    name="homelab_gpu_telemetry",
    description=(
        "Owner-only live GPU utilization and free-VRAM read through an "
        "explicitly configured strict-host-key SSH endpoint and fixed remote "
        "command. The remote identity must be non-sudo and ForceCommand "
        "restricted. No caller-supplied host or command is accepted; read-only."
    ),
    inputSchema={"type": "object", "properties": {}},
), Tool(
    name="homelab_discovery_candidates",
    description=(
        "Turn normalized Nmap evidence into transient review-only device "
        "candidates. This does not run Nmap, change NetBox, or perform any "
        "inventory or management write."
    ),
    inputSchema={"type": "object", "properties": {
        "evidence": {"type": "object"},
        "netbox": {"type": "object"},
    }, "required": ["evidence"]},
)]


def _read_token(path: str) -> str:
    token_path = Path(path)
    if not token_path.is_file() or token_path.is_symlink():
        raise ValueError("homelab token file must be a regular non-symlink file")
    mode = token_path.stat().st_mode & 0o777
    if mode not in {0o600, 0o640}:
        raise ValueError("homelab token file must be mode 0600 or 0640")
    token = token_path.read_bytes()
    if not token or len(token) > MAX_TOKEN_BYTES:
        raise ValueError("homelab token file is empty or exceeds the bounded size")
    return token.decode("utf-8").strip()


def _fetch(
    url: str, token_file: str = "", ca_file: str = "", proxmox_token_id: str = "",
    *, timeout_seconds: int = TIMEOUT_SECONDS,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
) -> dict:
    if not url:
        raise ValueError("homelab source is not configured")
    if not url.startswith(("http://", "https://")):
        raise ValueError("homelab source must use HTTP(S)")
    headers = {"Accept": "application/json"}
    if token_file:
        token = _read_token(token_file)
        headers["Authorization"] = (
            f"PVEAPIToken={proxmox_token_id}={token}"
            if proxmox_token_id
            else f"Bearer {token}"
        )
    request = Request(url, headers=headers, method="GET")
    context = ssl.create_default_context(cafile=ca_file) if ca_file else None
    with urlopen(request, timeout=timeout_seconds, context=context) as response:
        body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ValueError("homelab response exceeds bounded size")
    result = json.loads(body)
    if not isinstance(result, dict):
        raise ValueError("homelab response must be a JSON object")
    return result


def _normalize_kuma_status(payload: dict) -> dict:
    """Convert Kuma's public heartbeat payload into bounded monitor rows."""
    if isinstance(payload.get("monitors"), list):
        return payload
    groups = payload.get("publicGroupList")
    heartbeats = payload.get("heartbeatList")
    if not isinstance(groups, list) or not isinstance(heartbeats, dict):
        raise ValueError("Uptime Kuma heartbeat response has an unsupported shape")
    monitors = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        for monitor in group.get("monitorList", []):
            if not isinstance(monitor, dict) or not monitor.get("name"):
                continue
            monitor_id = str(monitor.get("id", ""))
            history = heartbeats.get(monitor_id, [])
            latest = history[-1] if isinstance(history, list) and history else {}
            if not isinstance(latest, dict):
                latest = {}
            raw_status = latest.get("status")
            status = "up" if raw_status == 1 else "down" if raw_status == 0 else "unknown"
            row = {
                "name": monitor["name"],
                "status": status,
                "last_updated": latest.get("time"),
                "monitor_type": monitor.get("type"),
            }
            if monitor.get("id") is not None:
                row["id"] = str(monitor["id"])
                row["source_identity"] = f"kuma:monitor:{monitor['id']}"
            # Uptime Kuma's public heartbeat includes a per-check response
            # time. Preserve only a finite, nonnegative, bounded sample; it is
            # not a network-wide measurement or a historical baseline.
            ping = latest.get("ping")
            if isinstance(ping, (int, float)) and not isinstance(ping, bool):
                import math
                if math.isfinite(ping) and 0 <= ping <= 60000:
                    row["ping_ms"] = ping
            monitors.append(row)
    return {"monitors": monitors}


def _read_identity_links() -> dict[str, int]:
    """Read an optional protected source-identity to NetBox-device crosswalk."""
    path_value = homelab_identity_links_file()
    if not path_value:
        return {}
    path = Path(path_value)
    if not path.is_file() or path.is_symlink():
        raise ValueError("homelab identity-link file must be a regular non-symlink file")
    if (path.stat().st_mode & 0o777) not in {0o600, 0o640}:
        raise ValueError("homelab identity-link file must be mode 0600 or 0640")
    if path.stat().st_size > MAX_IDENTITY_LINK_BYTES:
        raise ValueError("homelab identity-link file exceeds bounded size")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("homelab identity-link file is unreadable or invalid JSON") from exc
    if not isinstance(document, dict) or set(document) != {"links"} or not isinstance(document["links"], list):
        raise ValueError("homelab identity-link file must contain only a links array")
    links: dict[str, int] = {}
    for row in document["links"]:
        if not isinstance(row, dict) or set(row) != {"source_identity", "netbox_device_id"}:
            raise ValueError("homelab identity-link row has an unsupported shape")
        source_identity = row["source_identity"]
        device_id = row["netbox_device_id"]
        if (
            not isinstance(source_identity, str)
            or not source_identity
            or len(source_identity) > 256
            or isinstance(device_id, bool)
            or not isinstance(device_id, int)
            or device_id <= 0
            or source_identity in links
        ):
            raise ValueError("homelab identity-link row is invalid or duplicated")
        links[source_identity] = device_id
    return links


def _proxmox_source_identity(source_id: str, row: dict) -> str | None:
    resource_type = row.get("type")
    if not source_id or not isinstance(resource_type, str) or not resource_type:
        return None
    entity_id = row.get("id")
    if isinstance(entity_id, str) and "/" in entity_id:
        entity_id = entity_id.rsplit("/", 1)[1]
    if entity_id is None and resource_type == "node":
        entity_id = row.get("node")
    if entity_id is None:
        entity_id = row.get("vmid")
    return (
        f"proxmox:{source_id}:{resource_type}:{entity_id}"
        if entity_id is not None else None
    )


def _project_proxmox_guest_index(
    source_ids: tuple[str, ...],
    source_rows_by_id: dict[str, list[dict]],
    runtime_observations: list[dict],
    visibility_results: list[dict],
) -> dict:
    """Expose a bounded, source-keyed guest index for owner restore checks.

    The ordinary summary intentionally compacts and truncates resources for
    conversational use. This separate projection preserves stable Proxmox
    node and guest identities without adding addresses, credentials, or write paths.
    It never claims completeness unless both runtime and effective
    VM.Audit-scope reads are complete for that source.
    """
    endpoints = []
    runtime_by_source = {
        str(row.get("source") or ""): row
        for row in runtime_observations if isinstance(row, dict)
    }
    for index, source_id in enumerate(source_ids):
        label = source_id or f"endpoint-{index + 1}"
        stable_source_id = bool(re.fullmatch(r"[A-Za-z0-9._-]{1,80}", source_id or ""))
        runtime = runtime_by_source.get(f"Proxmox:{label}", {})
        visibility_result = (
            visibility_results[index]
            if index < len(visibility_results) and isinstance(visibility_results[index], dict)
            else {}
        )
        visibility = visibility_result.get("coverage") if isinstance(visibility_result.get("coverage"), dict) else {}
        source_rows = source_rows_by_id.get(label, [])
        guests = []
        nodes = []
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            identity = row.get("source_identity")
            if row.get("type") == "node":
                node_match = re.fullmatch(
                    rf"proxmox:{re.escape(label)}:node:([A-Za-z0-9._-]{{1,128}})",
                    str(identity or ""),
                )
                node = str(row.get("node") or (node_match.group(1) if node_match else ""))
                if not node_match or node != node_match.group(1):
                    continue
                raw_node_status = str(row.get("status") or "").casefold()
                node_status = "ONLINE" if raw_node_status == "online" else "OFFLINE" if raw_node_status == "offline" else "UNKNOWN"
                nodes.append({
                    "source_identity": identity,
                    "node": node,
                    "name": _bounded_text(row.get("name") or node, 120),
                    "status": node_status,
                })
                continue
            if row.get("type") not in {"qemu", "lxc"}:
                continue
            match = re.fullmatch(rf"proxmox:{re.escape(label)}:(?:qemu|lxc):([1-9][0-9]{{0,19}})", str(identity or ""))
            if not match:
                continue
            guest_id = match.group(1)
            node = str(row.get("node") or "")
            node_identity = (
                f"proxmox:{label}:node:{node}"
                if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", node) else None
            )
            raw_status = str(row.get("status") or "").casefold()
            status = "RUNNING" if raw_status == "running" else "STOPPED" if raw_status == "stopped" else "UNKNOWN"
            guests.append({
                "source_identity": identity,
                "node_identity": node_identity,
                "guest_type": row["type"],
                "guest_id": guest_id,
                "name": _bounded_text(row.get("name"), 120) or None,
                "node": _bounded_text(node, 120) or None,
                "status": status,
            })
        guests_truncated = len(guests) > 512
        nodes_truncated = len(nodes) > 128
        guests = guests[:512]
        nodes = nodes[:128]
        truncated = guests_truncated or nodes_truncated
        runtime_available = str(runtime.get("status") or "").upper() == "AVAILABLE"
        visibility_complete = (
            str(visibility.get("status") or "").upper() == "COMPLETE"
            and str(visibility.get("scope") or "").upper() == "ALL_GUESTS"
        )
        complete = runtime_available and visibility_complete and stable_source_id and not truncated
        endpoint_status = (
            "UNAVAILABLE" if not runtime_available else "COMPLETE" if complete else "PARTIAL"
        )
        endpoints.append({
            "source_id": label,
            "status": endpoint_status,
            "visibility_status": str(visibility.get("status") or "UNKNOWN").upper(),
            "visibility_scope": str(visibility.get("scope") or "UNKNOWN").upper(),
            "retrieved_at": runtime.get("retrieved_at"),
            "truncated": truncated,
            "guest_truncated": guests_truncated,
            "node_truncated": nodes_truncated,
            # VM.Audit completeness does not prove host-level Sys.Audit scope.
            # A returned node is observed, but an absent node is not proof of
            # an empty or complete node inventory.
            "node_inventory_status": (
                "OBSERVED" if runtime_available and bool(nodes) and not nodes_truncated
                else "UNKNOWN" if not runtime_available or not nodes else "PARTIAL"
            ),
            "nodes": nodes,
            "guests": guests,
        })
    status = "NOT_CONFIGURED" if not endpoints else (
        "COMPLETE" if all(row["status"] == "COMPLETE" for row in endpoints) else "PARTIAL"
    )
    return {"status": status, "endpoints": endpoints, "read_only": True}


def _project_proxmox_node_metrics(
    source_ids: tuple[str, ...],
    source_rows_by_id: dict[str, list[dict]],
    source_observations: list[dict],
    resources: list[dict],
    identity_links: dict[str, int] | None = None,
) -> dict:
    """Project observed Proxmox node CPU/memory without asserting full coverage."""
    observations = {
        str(row.get("source") or ""): row
        for row in source_observations if isinstance(row, dict)
    }
    names_by_identity: dict[str, str] = {}
    for resource in resources if isinstance(resources, list) else []:
        if not isinstance(resource, dict):
            continue
        identity = resource.get("identity") if isinstance(resource.get("identity"), dict) else {}
        source_identities = identity.get("source_identities")
        proxmox_identities = source_identities.get("proxmox") if isinstance(source_identities, dict) else []
        name = _bounded_text(resource.get("name"), 120)
        if name and isinstance(proxmox_identities, list):
            for source_identity in proxmox_identities:
                if isinstance(source_identity, str) and source_identity:
                    names_by_identity[source_identity] = name

    endpoints = []
    identity_links = identity_links if isinstance(identity_links, dict) else {}
    for index, source_id in enumerate(source_ids):
        label = source_id or f"endpoint-{index + 1}"
        stable_source_id = bool(re.fullmatch(r"[A-Za-z0-9._-]{1,80}", source_id or ""))
        observation = observations.get(f"Proxmox:{label}", {})
        configured_status = str(observation.get("status") or "UNKNOWN").upper()
        source_status = configured_status
        error_code = None
        if not stable_source_id:
            source_status = "UNKNOWN"
            error_code = "UNSTABLE_SOURCE_IDENTITY"
        elif configured_status == "AVAILABLE" and not observation.get("retrieved_at"):
            source_status = "UNKNOWN"
            error_code = "MISSING_SOURCE_TIMESTAMP"
        rows = source_rows_by_id.get(label, []) if isinstance(source_rows_by_id, dict) else []
        node_rows = []
        truncated = False
        if source_status == "AVAILABLE":
            observed_nodes = [
                row for row in rows if isinstance(row, dict) and row.get("type") == "node"
            ]
            truncated = len(observed_nodes) > 64
            for row in observed_nodes[:64]:
                node = row.get("node")
                if not isinstance(node, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", node):
                    continue
                identity = row.get("source_identity") or _proxmox_source_identity(label, row)
                raw_status = str(row.get("status") or "").casefold()
                status = "ONLINE" if raw_status == "online" else "OFFLINE" if raw_status == "offline" else "UNKNOWN"
                item = {
                    "source_identity": identity,
                    "node": node,
                    "name": names_by_identity.get(identity) or _bounded_text(row.get("name"), 120) or node,
                    "status": status,
                    "observed_at": observation.get("retrieved_at"),
                }
                linked_device_id = identity_links.get(identity)
                if isinstance(linked_device_id, int) and not isinstance(linked_device_id, bool) and linked_device_id > 0:
                    item["canonical_id"] = f"netbox:device:{linked_device_id}"
                    item["identity_status"] = "LINKED"
                else:
                    item["canonical_id"] = None
                    item["identity_status"] = "UNLINKED"
                if status == "ONLINE":
                    cpu = row.get("cpu")
                    if isinstance(cpu, (int, float)) and not isinstance(cpu, bool) and 0 <= cpu <= 1:
                        item["cpu_fraction"] = float(cpu)
                    used, total = row.get("mem"), row.get("maxmem")
                    if (
                        isinstance(used, int) and not isinstance(used, bool) and used >= 0
                        and isinstance(total, int) and not isinstance(total, bool) and total > 0
                        and used <= total
                    ):
                        item["memory_used_bytes"] = used
                        item["memory_total_bytes"] = total
                node_rows.append(item)
        endpoints.append({
            "source_id": source_id or None,
            "status": source_status,
            "source_status": configured_status,
            "error_code": error_code,
            "retrieved_at": observation.get("retrieved_at"),
            "node_inventory_status": (
                "OBSERVED" if source_status == "AVAILABLE" and node_rows and not truncated
                else "PARTIAL" if source_status == "AVAILABLE" and truncated
                else "UNKNOWN"
            ),
            "truncated": truncated,
            "nodes": node_rows,
        })
    statuses = [row["status"] for row in endpoints]
    available = sum(state == "AVAILABLE" for state in statuses)
    if not endpoints:
        status = "NOT_CONFIGURED"
    elif all(state == "AVAILABLE" for state in statuses):
        status = "READABLE"
    elif available:
        status = "PARTIAL"
    elif all(state == "UNKNOWN" for state in statuses):
        status = "UNKNOWN"
    elif all(state == "UNAVAILABLE" for state in statuses):
        status = "UNAVAILABLE"
    else:
        status = "UNAVAILABLE"
    return {
        "status": status,
        "coverage": "observed node rows from configured Proxmox cluster/resources sources; not a complete node inventory",
        "endpoints": endpoints,
        "read_only": True,
        "writes_performed": False,
    }


def _proxmox_permissions_url(resources_url: str) -> str:
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


def _proxmox_guest_visibility(payload: dict) -> dict:
    """State whether effective read ACLs cover all or only selected guests."""
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


def _aggregate_proxmox_guest_visibility(rows: list[dict]) -> dict:
    states = [row.get("status", "UNKNOWN") for row in rows]
    scopes = {row.get("scope", "UNKNOWN") for row in rows}
    status = ("NOT_CONFIGURED" if not rows else "COMPLETE" if all(s == "COMPLETE" for s in states)
              else "PARTIAL" if any(s == "PARTIAL" for s in states) else "UNKNOWN")
    scope = next(iter(scopes)) if len(scopes) == 1 else "MIXED" if scopes else "UNKNOWN"
    return {"status": status, "scope": scope}


def _read_proxmox_guest_visibility(
    index: int, url: str, token_file: str, token_id: str, source_id: str, ca_file: str,
) -> dict:
    label = source_id or f"endpoint-{index + 1}"
    source = f"Proxmox guest visibility ({label})"
    try:
        payload = _fetch(_proxmox_permissions_url(url), token_file, ca_file, token_id)
        retrieved_at = _retrieved_at()
        coverage = _proxmox_guest_visibility(payload)
        return {
            "coverage": coverage,
            "observation": {"source": source, **coverage, "retrieved_at": retrieved_at},
        }
    except Exception as exc:
        retrieved_at = _retrieved_at()
        return {
            "coverage": {"status": "UNKNOWN", "scope": "UNKNOWN"},
            "observation": {"source": source, "status": "UNKNOWN", "scope": "UNKNOWN",
                            "retrieved_at": retrieved_at, "error_code": type(exc).__name__},
        }


def _retrieved_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _kuma_config_url() -> str:
    explicit = os.environ.get("HADES_KUMA_CONFIG_URL", "").strip()
    if explicit:
        return explicit
    base = os.environ.get("HADES_UPTIME_KUMA_URL", "").rstrip("/")
    slug = os.environ.get("HADES_UPTIME_KUMA_STATUS_SLUG", "").strip("/")
    return f"{base}/api/status-page/{slug}" if base and slug else ""


def homelab_summary() -> dict:
    values: list[dict | None] = []
    errors: list[str] = []
    source_observations: list[dict] = []
    proxmox_value: dict | None = None
    netbox_value: dict | None = None
    proxmox_token_config_valid = True
    configured_proxmox_source_ids: tuple[str, ...] = ()
    proxmox_guest_rows_by_source: dict[str, list[dict]] = {}
    guest_visibility_results: list[dict] = []
    try:
        specs = proxmox_specs()
    except ValueError as exc:
        specs = ()
        errors.append(f"Proxmox configuration invalid: {exc}")
        source_observations.append({
            "source": "Proxmox", "status": "INVALID_CONFIGURATION", "retrieved_at": None,
        })
    if specs:
        rows: list[dict] = []
        proxmox_errors: list[str] = []
        ca_file = os.environ.get("HADES_PROXMOX_CA_FILE", "")
        try:
            source_ids = proxmox_source_ids()
        except ValueError as exc:
            source_ids = tuple("" for _ in specs)
            proxmox_errors.append(f"Proxmox source identity configuration invalid: {type(exc).__name__}")
        configured_proxmox_source_ids = source_ids
        try:
            token_ids = proxmox_token_ids()
        except ValueError as exc:
            token_ids = tuple("" for _ in specs)
            proxmox_token_config_valid = False
            proxmox_errors.append(f"Proxmox token configuration invalid: {type(exc).__name__}")
        for index, (url, token_file) in enumerate(specs):
            source_label = source_ids[index] or f"endpoint-{index + 1}"
            if not url:
                source_observations.append({
                    "source": f"Proxmox:{source_label}",
                    "status": "NOT_CONFIGURED",
                    "retrieved_at": None,
                })
                continue
            if not proxmox_token_config_valid:
                source_observations.append({
                    "source": f"Proxmox:{source_label}", "status": "INVALID_CONFIGURATION",
                    "retrieved_at": None,
                })
                continue
            try:
                payload = _fetch(url, token_file, ca_file, token_ids[index])
                source_rows = [row for row in payload.get("data", []) if isinstance(row, dict)]
                indexed_source_rows = []
                for source_row in source_rows:
                    row = dict(source_row)
                    source_identity = _proxmox_source_identity(source_ids[index], row)
                    if source_identity:
                        row["source_identity"] = source_identity
                    rows.append(row)
                    indexed_source_rows.append(row)
                proxmox_guest_rows_by_source[source_label] = indexed_source_rows
                source_observations.append({
                    "source": f"Proxmox:{source_label}",
                    "status": "AVAILABLE",
                    "retrieved_at": _retrieved_at(),
                    "rows": len(source_rows),
                })
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                message = f"Proxmox:{source_label} source unavailable: {exc}"
                errors.append(message)
                proxmox_errors.append(message)
                source_observations.append({
                    "source": f"Proxmox:{source_label}",
                    "status": "UNAVAILABLE",
                    "retrieved_at": None,
                })
        proxmox_value = {"data": rows}
        if proxmox_errors:
            proxmox_value["errors"] = proxmox_errors
    elif not source_observations:
        errors.append("Proxmox source is not configured")
        source_observations.append({
            "source": "Proxmox", "status": "NOT_CONFIGURED", "retrieved_at": None,
        })
    values.append(proxmox_value)
    guest_visibility_rows = []
    if specs:
        try:
            source_ids = proxmox_source_ids()
        except ValueError:
            source_ids = tuple("" for _ in specs)
        try:
            token_ids = proxmox_token_ids()
        except ValueError:
            token_ids = tuple("" for _ in specs)
        ca_file = os.environ.get("HADES_PROXMOX_CA_FILE", "")
        requests = [
            (index, url, token_file, token_ids[index], source_ids[index], ca_file)
            for index, (url, token_file) in enumerate(specs)
        ]
        if not proxmox_token_config_valid:
            visibility_results = [{
                "coverage": {"status": "UNKNOWN", "scope": "UNKNOWN"},
                "observation": {"source": f"Proxmox guest visibility ({source_ids[index] or f'endpoint-{index + 1}'})",
                                "status": "UNKNOWN", "scope": "UNKNOWN", "retrieved_at": None,
                                "error_code": "INVALID_CONFIGURATION"},
            } for index in range(len(requests))]
        else:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(8, len(requests))) as pool:
                visibility_results = list(pool.map(lambda args: _read_proxmox_guest_visibility(*args), requests))
        guest_visibility_results = visibility_results
        guest_visibility_rows = [result["coverage"] for result in visibility_results]
        source_observations.extend(result["observation"] for result in visibility_results)
    visibility_aggregate = _aggregate_proxmox_guest_visibility(guest_visibility_rows)
    result_guest_visibility = {
        "status": visibility_aggregate["status"],
        "scope": visibility_aggregate["scope"],
        "endpoints": guest_visibility_rows,
        "read_only": True,
    }
    for label, (url, token_file) in zip(("NetBox", "Uptime Kuma"), supporting_source_specs(), strict=True):
        if not url:
            values.append(None)
            errors.append(f"{label} source is not configured")
            source_observations.append({
                "source": label, "status": "NOT_CONFIGURED", "retrieved_at": None,
            })
            continue
        try:
            value = _fetch(url, token_file)
            if label == "Uptime Kuma" and "monitors" not in value:
                config_url = _kuma_config_url()
                if not config_url:
                    raise ValueError("Uptime Kuma status-page config URL is not configured")
                config_value = _fetch(config_url, token_file)
                merged = dict(config_value)
                merged.update(value)
                value = merged
            normalized_value = _normalize_kuma_status(value) if label == "Uptime Kuma" else value
            values.append(normalized_value)
            source_observations.append({
                "source": label,
                "status": "AVAILABLE",
                "retrieved_at": _retrieved_at(),
                "rows": len(normalized_value.get("results", [])) if label == "NetBox" else len(normalized_value.get("monitors", [])),
            })
            if label == "NetBox":
                netbox_value = value
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            values.append(None)
            errors.append(f"{label} source unavailable: {exc}")
            source_observations.append({
                "source": label, "status": "UNAVAILABLE", "retrieved_at": None,
            })
    try:
        identity_links = _read_identity_links()
    except (OSError, ValueError) as exc:
        identity_links = {}
        errors.append(str(exc))
    result = summarize(*values, identity_links=identity_links)
    if errors and result["status"] == "OK":
        result["status"] = "PARTIAL"
    result["source_observations"] = source_observations
    # Preserve the established overlay-facing field while the canonical
    # candidate uses the more descriptive observation name.
    result["sources"] = source_observations
    result["proxmox_guest_visibility"] = result_guest_visibility
    result["proxmox_guest_inventory"] = _project_proxmox_guest_index(
        configured_proxmox_source_ids,
        proxmox_guest_rows_by_source,
        source_observations,
        guest_visibility_results,
    )
    result["proxmox_node_metrics"] = _project_proxmox_node_metrics(
        configured_proxmox_source_ids,
        proxmox_guest_rows_by_source,
        source_observations,
        result.get("resources", []),
        identity_links=identity_links,
    )
    if visibility_aggregate["status"] in {"PARTIAL", "UNKNOWN"} and result["status"] == "OK":
        result["status"] = "PARTIAL"
    from services import project_netbox_services

    service_url, service_token_file = netbox_services_spec()
    if service_url:
        try:
            service_payload = _fetch(service_url, service_token_file)
            result["service_catalog"] = project_netbox_services(
                service_payload, netbox_value
            )
            result["service_catalog"]["retrieved_at"] = _retrieved_at()
        except (OSError, ValueError, json.JSONDecodeError):
            result["service_catalog"] = {
                "status": "UNAVAILABLE",
                "source": "NetBox application services",
                "retrieved_at": None,
                "services": [],
                "inventory_is_not_liveness": True,
                "writes_performed": False,
                "limitation": "NetBox application-service inventory could not be read.",
            }
    else:
        result["service_catalog"] = {
            "status": "NOT_CONFIGURED",
            "source": "NetBox application services",
            "retrieved_at": None,
            "services": [],
            "inventory_is_not_liveness": True,
            "writes_performed": False,
            "limitation": "NetBox application-service endpoint is not configured.",
        }
    result["source_counts"]["netbox_service_rows"] = len(
        result["service_catalog"].get("services", [])
    )
    # Keep the common owner answer bounded. The raw composed resources can
    # contain many inventory-only rows and made a small local model spend its
    # entire turn repeating JSON instead of answering. Preserve the authority
    # and decision fields needed for status/location questions while leaving
    # the full capability matrix to homelab_compute_capabilities().
    compact_resources = []
    for resource in result.get("resources", []):
        inventory = resource.get("inventory") or {}
        availability = resource.get("availability") or {}
        compact_resources.append({
            "name": resource.get("name"),
            "identity": resource.get("identity"),
            "runtime_status": resource.get("runtime_status"),
            "currently_online": resource.get("currently_online"),
            "runtime": resource.get("runtime"),
            "inventory_device_id": inventory.get("id"),
            "related_inventory_device_id": resource.get("related_inventory_device_id"),
            "primary_ip": inventory.get("primary_ip"),
            "role": inventory.get("role"),
            "availability_status": availability.get("status"),
            "availability_freshness": resource.get("availability_freshness"),
            "conflicts": resource.get("conflicts", []),
        })
    # Keep the detailed index useful for location questions without allowing a
    # large inventory to dominate the model context. The complete online and
    # inventory-only name lists above remain authoritative; this is only the
    # optional per-resource detail view.
    resource_limit = 4
    if len(compact_resources) > resource_limit:
        result["resources_truncated"] = {
            "returned": resource_limit,
            "total": len(compact_resources),
            "reason": "use homelab_compute_capabilities or a targeted follow-up for more detail",
        }
        compact_resources = compact_resources[:resource_limit]
    result["resources"] = compact_resources
    for field, limit in (
        ("online_names", 24),
        ("inventory_only_names", 12),
        ("availability_summary", 12),
    ):
        values = result.get(field)
        if isinstance(values, list) and len(values) > limit:
            result[f"{field}_truncated"] = {
                "returned": limit,
                "total": len(values),
            }
            result[field] = values[:limit]
    result["supplemental_hardware"] = {
        "status": "AVAILABLE",
        "source": "observed capability matrix",
        "availability_not_provided": True,
        "use_homelab_compute_capabilities_for_details": True,
    }
    if errors:
        result["errors"] = errors
    return result


def _capability_matrix_freshness(observed_at: object, *, now: datetime | None = None) -> str:
    """Classify observed hardware facts with the bounded seven-day freshness window."""
    if not isinstance(observed_at, str) or not observed_at.strip():
        return "UNKNOWN"
    try:
        observed = datetime.fromisoformat(observed_at.strip().replace("Z", "+00:00"))
    except ValueError:
        return "UNKNOWN"
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if observed > current:
        return "UNKNOWN"
    return "FRESH" if current - observed <= timedelta(days=7) else "STALE"


def homelab_compute_capabilities() -> dict:
    """Return observed hardware facts without claiming live availability."""
    from config import capability_matrix_file

    path_value = capability_matrix_file()
    if not path_value:
        return {
            "status": "UNAVAILABLE",
            "freshness": "UNKNOWN",
            "source": "observed capability matrix",
            "error": "capability matrix is not configured",
            "read_only": True,
        }
    path = Path(path_value)
    if not path.is_file() or path.is_symlink():
        return {
            "status": "UNAVAILABLE",
            "freshness": "UNKNOWN",
            "source": "observed capability matrix",
            "error": "capability matrix is not a regular file",
            "read_only": True,
        }
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("capability matrix exceeds bounded size")
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return {
            "status": "UNAVAILABLE",
            "freshness": "UNKNOWN",
            "source": "observed capability matrix",
            "error": f"capability matrix could not be read: {exc}",
            "read_only": True,
        }
    machines = document.get("machines") if isinstance(document, dict) else None
    if not isinstance(machines, list):
        raise ValueError("capability matrix machines must be a list")
    rows = []
    for machine in machines:
        if not isinstance(machine, dict) or not isinstance(machine.get("name"), str):
            raise ValueError("capability matrix contains an invalid machine")
        row = {
            key: machine.get(key)
            for key in (
                "name", "address", "os", "cpu", "ram_gib", "gpus",
                "nvidia_driver", "cuda_container_capability",
                "ssh", "role",
            )
        }
        # Preserve the observed matrix annotation without exposing the
        # authority-bearing field name used by Proxmox reconciliation.
        row["matrix_status"] = machine.get("runtime_status")
        rows.append(row)
    return {
        "status": "OK",
        # Keep successful source access separate from observed-data freshness.
        "freshness": _capability_matrix_freshness(document.get("observed_at")),
        "source": "tracked observed capability matrix",
        "availability_not_provided": True,
        "observed_at": document.get("observed_at"),
        "authority": {
            "hardware": "observed capability matrix",
            "runtime": "Proxmox",
            "inventory": "NetBox",
            "availability": "Uptime Kuma",
        },
        "machines": rows,
        "placement_rule": (
            "Hardware inventory does not imply current availability, driver, "
            "VRAM, CUDA, or free capacity; reconcile those facts with live "
            "sources and acceptance evidence before placement."
        ),
        "liveness_rule": (
            "Never label a machine online from this response. Proxmox is the "
            "only authority for current runtime status; matrix_status is "
            "historical/observed inventory metadata, not liveness."
        ),
        "read_only": True,
    }


def homelab_gpu_telemetry() -> dict:
    """Read live GPU state from the protected fixed-command SSH profile."""
    return read_gpu_telemetry(gpu_telemetry_config_file())


def _read_inference_endpoint(endpoint: dict[str, str], links: dict[str, int]) -> dict:
    """Read one provider's bounded model catalog and optional residency."""
    identity = f"inference:{endpoint['id']}"
    base = endpoint["url"].rstrip("/") + "/"
    checked_at = _retrieved_at()
    try:
        if endpoint["provider"] == "openai-compatible":
            catalog = _fetch(urljoin(base, "v1/models"), endpoint["token_file"], endpoint["ca_file"],
                             timeout_seconds=4, max_response_bytes=512 * 1024).get("data")
            if not isinstance(catalog, list) or len(catalog) > 512:
                raise ValueError("inference model catalog has an invalid shape")
            models = [{"name": str(row["id"])[:256]} for row in catalog
                      if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"]]
            loaded, loaded_status = [], "UNSUPPORTED"
        else:
            catalog = _fetch(urljoin(base, "api/tags"), endpoint["token_file"], endpoint["ca_file"],
                             timeout_seconds=4, max_response_bytes=512 * 1024).get("models")
            if not isinstance(catalog, list) or len(catalog) > 512:
                raise ValueError("inference model catalog has an invalid shape")
            models = []
            for row in catalog:
                if not isinstance(row, dict) or not isinstance(row.get("name"), str):
                    continue
                models.append({"name": row["name"][:256],
                               "size_bytes": row.get("size") if type(row.get("size")) is int and row["size"] >= 0 else None,
                               "modified_at": str(row.get("modified_at") or "")[:64] or None})
            try:
                running = _fetch(urljoin(base, "api/ps"), endpoint["token_file"], endpoint["ca_file"],
                                 timeout_seconds=4, max_response_bytes=512 * 1024).get("models")
                if not isinstance(running, list) or len(running) > 512:
                    raise ValueError("inference residency response has an invalid shape")
                loaded = [{"name": row["name"][:256],
                           "size_vram_bytes": row.get("size_vram") if type(row.get("size_vram")) is int and row["size_vram"] >= 0 else None}
                          for row in running if isinstance(row, dict) and isinstance(row.get("name"), str)]
                loaded_status = "CURRENT"
            except Exception:
                loaded, loaded_status = [], "UNKNOWN"
        return {"source_identity": identity, "netbox_device_id": links.get(identity),
                "identity_status": "LINKED" if identity in links else "UNLINKED",
                "provider": endpoint["provider"], "status": "READABLE" if loaded_status != "UNKNOWN" else "PARTIAL",
                "checked_at": checked_at, "models": models, "loaded_models": loaded,
                "loaded_status": loaded_status,
                "health_scope": "provider catalog/residency only; no generation request was made",
                "read_only": True}
    except Exception as exc:
        return {"source_identity": identity, "netbox_device_id": links.get(identity),
                "identity_status": "LINKED" if identity in links else "UNLINKED",
                "provider": endpoint["provider"], "status": "UNAVAILABLE", "checked_at": checked_at,
                "models": [], "loaded_models": [], "loaded_status": "UNKNOWN",
                "error_code": type(exc).__name__, "read_only": True}


def homelab_inference_inventory() -> dict:
    """Query configured inference providers concurrently, without mutation."""
    try:
        endpoints = inference_endpoint_specs()
        links = _read_identity_links()
    except (OSError, ValueError, json.JSONDecodeError):
        return {"status": "CONFIGURATION_ERROR", "endpoints": [], "read_only": True}
    if not endpoints:
        return {"status": "NOT_CONFIGURED", "endpoints": [], "read_only": True,
                "retrieved_at": _retrieved_at()}
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(8, len(endpoints))) as pool:
        rows = list(pool.map(lambda endpoint: _read_inference_endpoint(endpoint, links), endpoints))
    # Keep the crosswalk explicit in the public read shape. Do not infer a
    # host from a provider label or IP address. Resolve the configured NetBox
    # IDs through NetBox itself; this works even when the compact summary
    # omits that inventory row.
    for row in rows:
        device_id = row.get("netbox_device_id")
        if (
            row.get("identity_status") == "LINKED"
            and isinstance(device_id, int) and not isinstance(device_id, bool)
            and device_id > 0
        ):
            row["node_identity"] = f"netbox:device:{device_id}"
    linked_names = resolve_inference_node_labels({"endpoints": rows})
    for row in rows:
        identity = row.get("node_identity")
        if row.get("identity_status") == "LINKED" and identity in linked_names:
            row["node_name"] = linked_names[identity]
    states = [row["status"] for row in rows]
    status = "READABLE" if all(state == "READABLE" for state in states) else (
        "UNAVAILABLE" if all(state == "UNAVAILABLE" for state in states) else "PARTIAL")
    return {"status": status, "source": "configured provider-native inference APIs",
            "retrieved_at": _retrieved_at(), "endpoints": rows, "read_only": True}


def homelab_inference_capacity() -> dict:
    """Read all canonical inputs needed for an owner capacity answer."""
    from concurrent.futures import ThreadPoolExecutor

    readers = {
        "summary": homelab_summary,
        "hardware_inventory": homelab_compute_capabilities,
        "inference": homelab_inference_inventory,
        "gpu_telemetry": homelab_gpu_telemetry,
    }
    def bounded_read(reader):
        try:
            value = reader()
            return value if isinstance(value, dict) else {
                "status": "INVALID_RESPONSE", "read_only": True,
            }
        except Exception as exc:
            return {"status": "UNAVAILABLE", "error_code": type(exc).__name__,
                    "retrieved_at": _retrieved_at(), "read_only": True}

    with ThreadPoolExecutor(max_workers=len(readers)) as pool:
        futures = {name: pool.submit(bounded_read, reader) for name, reader in readers.items()}
        result = {name: future.result() for name, future in futures.items()}
    states = [
        str(value.get("status", "UNKNOWN")).upper()
        for value in result.values() if isinstance(value, dict)
    ]
    complete = all(state in {"OK", "READABLE"} for state in states)
    return {
        "status": "READABLE" if complete else "PARTIAL",
        "retrieved_at": _retrieved_at(),
        **result,
        "answer_contract": {
            "liveness_source": "Proxmox runtime only",
            "hardware_source": "observed capability matrix; not live availability",
            "gpu_values": "point-in-time live telemetry only",
            "provider_catalog": "does not prove generation or GPU residency unless explicitly returned",
            "model_fit": "not calculated; free VRAM is not a fit guarantee",
            "writes_performed": False,
        },
        "read_only": True,
    }



def _bounded_text(value: object, limit: int = 256) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join("".join(char if char.isprintable() else " " for char in value).split())
    return normalized[:limit] or None


def _source_error_code(exc: BaseException) -> str:
    """Return useful failure classes without exposing exception text or URLs."""
    from urllib.error import HTTPError, URLError

    if isinstance(exc, HTTPError):
        return f"HTTP_{exc.code}"
    if isinstance(exc, URLError) and isinstance(exc.reason, TimeoutError):
        return "TIMEOUT"
    if isinstance(exc, (TimeoutError,)):
        return "TIMEOUT"
    if isinstance(exc, URLError):
        return "SOURCE_UNREACHABLE"
    if isinstance(exc, json.JSONDecodeError):
        return "INVALID_JSON"
    if isinstance(exc, ValueError):
        return "INVALID_RESPONSE_OR_CONFIGURATION"
    if isinstance(exc, OSError):
        return "SOURCE_IO_ERROR"
    return "SOURCE_ERROR"


def _proxmox_guest_task_scope(payload: dict) -> dict:
    """Return the subset of guest IDs safe to include from a task listing."""
    permissions = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(permissions, dict):
        raise ValueError("Proxmox effective-permissions response has an invalid shape")
    broad = False
    denied: set[str] = set()
    explicit: set[str] = set()
    has_non_enumerable_scope = False
    has_non_enumerable_exclusion = False
    for path, grants in permissions.items():
        if not isinstance(path, str) or not isinstance(grants, dict):
            continue
        vm_match = re.fullmatch(r"/vms/([1-9][0-9]{0,19})", path)
        if vm_match and _permission_enabled(grants.get("NoAccess")):
            denied.add(vm_match.group(1))
        elif _permission_enabled(grants.get("NoAccess")) and (
            path in {"/", "/vms"} or path.startswith(("/vms/", "/pool/"))
        ):
            has_non_enumerable_exclusion = True
        if not _permission_enabled(grants.get("VM.Audit")):
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


def homelab_backup_status() -> dict:
    """Read vzdump schedules and only archived tasks in effective VM.Audit scope."""
    from concurrent.futures import ThreadPoolExecutor
    from config import proxmox_specs, proxmox_source_ids, proxmox_token_ids

    try:
        specs = proxmox_specs()
        token_ids = proxmox_token_ids()
        source_ids = proxmox_source_ids()
    except (OSError, ValueError):
        return {
            "status": "CONFIGURATION_ERROR",
            "source": "Proxmox vzdump jobs and archived tasks",
            "endpoints": [],
            "read_only": True,
            "coverage": "proxmox-vzdump-only",
        }
    if not specs:
        return {
            "status": "NOT_CONFIGURED",
            "source": "Proxmox vzdump jobs and archived tasks",
            "endpoints": [],
            "read_only": True,
            "coverage": "proxmox-vzdump-only",
        }

    ca_file = os.environ.get("HADES_PROXMOX_CA_FILE", "")
    endpoints = []
    for (resources_url, token_file), token_id, source_id in zip(
        specs, token_ids, source_ids, strict=True
    ):
        started = time.monotonic()
        parsed = urlsplit(resources_url)
        path = parsed.path.rstrip("/")
        suffix = "/cluster/resources"
        if (
            parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not path.endswith(suffix)
        ):
            endpoints.append({
                "source_id": source_id,
                "status": "UNAVAILABLE",
                "jobs_status": "UNKNOWN",
                "tasks_status": "UNKNOWN",
                "task_scope": "UNKNOWN",
                "error_code": "INVALID_PROXMOX_RESOURCES_URL",
                "jobs": [],
                "tasks": [],
                "unattributed_tasks": [],
            })
            continue
        api_base = urlunsplit((parsed.scheme, parsed.netloc, path[:-len(suffix)], "", ""))
        jobs = []
        tasks = []
        unattributed_tasks = []
        jobs_status = "UNAVAILABLE"
        tasks_status = "UNAVAILABLE"
        jobs_truncated = False
        nodes_truncated = False
        tasks_truncated = False
        error_codes = []
        task_scope = {"scope": "UNKNOWN", "all_guests": False, "guest_ids": []}
        try:
            permissions_payload = _fetch(
                _proxmox_permissions_url(resources_url), token_file, ca_file, token_id,
            )
            task_scope = _proxmox_guest_task_scope(permissions_payload)
        except (OSError, ValueError, UnicodeError) as exc:
            error_codes.append(_source_error_code(exc))
        try:
            job_payload = _fetch(
                urljoin(api_base.rstrip("/") + "/", "cluster/backup"),
                token_file, ca_file, token_id,
            )
            raw_jobs = job_payload.get("data")
            if not isinstance(raw_jobs, list):
                raise ValueError("Proxmox backup job response has an unsupported shape")
            jobs_truncated = len(raw_jobs) > 64
            for raw in raw_jobs[:64]:
                if not isinstance(raw, dict):
                    continue
                item = {}
                for key in ("id", "schedule", "storage", "node", "mode"):
                    value = raw.get(key)
                    if isinstance(value, str):
                        bounded = _bounded_text(value, 128)
                        if bounded:
                            item[key] = bounded
                vmid = raw.get("vmid")
                if isinstance(vmid, str):
                    ids = [part for part in re.split(r"[,;\s]+", vmid) if re.fullmatch(r"[1-9][0-9]{0,8}", part)]
                    if ids:
                        item["vmids"] = ids[:32]
                all_guests = raw.get("all")
                if isinstance(all_guests, (bool, int)) and all_guests in {0, 1, False, True}:
                    item["all_guests"] = bool(all_guests)
                enabled = raw.get("enabled")
                if isinstance(enabled, (bool, int)) and enabled in {0, 1, False, True}:
                    item["enabled"] = bool(enabled)
                jobs.append(item)
            jobs_status = "PARTIAL" if jobs_truncated else "HEALTHY"
        except (OSError, ValueError, UnicodeError) as exc:
            error_codes.append(_source_error_code(exc))

        try:
            runtime_payload = _fetch(resources_url, token_file, ca_file, token_id)
            raw_resources = runtime_payload.get("data")
            if not isinstance(raw_resources, list):
                raise ValueError("Proxmox runtime response has an unsupported shape")
            all_nodes = sorted({
                row.get("node") for row in raw_resources
                if isinstance(row, dict) and row.get("type") == "node"
                and isinstance(row.get("node"), str)
                and re.fullmatch(r"[A-Za-z0-9._-]{1,128}", row["node"])
            })
            nodes_truncated = len(all_nodes) > 16
            nodes = all_nodes[:16]
            if not nodes:
                raise ValueError("Proxmox runtime response contains no readable nodes")
            can_read_guest_tasks = (
                task_scope.get("all_guests") is True
                or bool(task_scope.get("guest_ids"))
            )
            if not can_read_guest_tasks:
                tasks_status = "UNKNOWN"
                task_states = []
            else:
                def read_tasks(node):
                    try:
                        endpoint = urljoin(
                            api_base.rstrip("/") + "/",
                            f"nodes/{quote(node, safe='')}/tasks?source=archive&limit=20&typefilter=vzdump",
                        )
                        payload = _fetch(endpoint, token_file, ca_file, token_id)
                        data = payload.get("data")
                        if not isinstance(data, list):
                            raise ValueError("Proxmox task response has an unsupported shape")
                        normalized = []
                        unattributed = []
                        excluded_rows = 0
                        allowed_ids = set(task_scope.get("guest_ids") or [])
                        denied_ids = set(task_scope.get("excluded_guest_ids") or [])
                        for row in data[:20]:
                            if not isinstance(row, dict):
                                continue
                            raw_guest_id = row.get("id")
                            if raw_guest_id is None or raw_guest_id == "":
                                # Keep aggregate/job-level evidence separate:
                                # without a guest ID it cannot prove that any
                                # specific VM or container was backed up.
                                raw_status = str(row.get("status") or "").strip().upper()
                                status = "OK" if raw_status == "OK" else (
                                    "RUNNING" if raw_status == "RUNNING" else
                                    "ERROR" if raw_status.startswith("ERROR") else "UNKNOWN"
                                )
                                item = {"node": node, "status": status}
                                for key in ("starttime", "endtime"):
                                    value = row.get(key)
                                    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                                        item[key] = value
                                if "endtime" in item:
                                    item["finished_at"] = datetime.fromtimestamp(
                                        item["endtime"], timezone.utc,
                                    ).isoformat()
                                unattributed.append(item)
                                continue
                            guest_id = row.get("id")
                            guest_id = (
                                guest_id if isinstance(guest_id, str)
                                and re.fullmatch(r"[1-9][0-9]{0,8}", guest_id)
                                else None
                            )
                            if task_scope.get("all_guests") is True:
                                if guest_id in denied_ids:
                                    excluded_rows += 1
                                    continue
                            elif guest_id not in allowed_ids:
                                excluded_rows += 1
                                continue
                            raw_status = str(row.get("status") or "").strip().upper()
                            status = "OK" if raw_status == "OK" else (
                                "RUNNING" if raw_status == "RUNNING" else
                                "ERROR" if raw_status.startswith("ERROR") else "UNKNOWN"
                            )
                            item = {"node": node, "status": status}
                            if guest_id:
                                item["guest_id"] = guest_id
                            for key in ("starttime", "endtime"):
                                value = row.get(key)
                                if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                                    item[key] = value
                            if "endtime" in item:
                                item["finished_at"] = datetime.fromtimestamp(
                                    item["endtime"], timezone.utc,
                                ).isoformat()
                            normalized.append(item)
                        return "HEALTHY", normalized, unattributed, None, excluded_rows
                    except (OSError, ValueError, UnicodeError, OverflowError) as exc:
                        return "UNAVAILABLE", [], [], _source_error_code(exc), 0

                with ThreadPoolExecutor(max_workers=min(8, len(nodes))) as pool:
                    task_reads = list(pool.map(read_tasks, nodes))
                task_states = [state for state, _, _, _, _ in task_reads]
                excluded_task_rows = 0
                for state, node_tasks, node_unattributed, error, excluded_rows in task_reads:
                    tasks.extend(node_tasks)
                    unattributed_tasks.extend(node_unattributed)
                    excluded_task_rows += excluded_rows
                    if error:
                        error_codes.append(error)
                tasks.sort(key=lambda row: row.get("endtime", row.get("starttime", 0)), reverse=True)
                unattributed_tasks.sort(
                    key=lambda row: row.get("endtime", row.get("starttime", 0)),
                    reverse=True,
                )
                tasks_truncated = len(tasks) + len(unattributed_tasks) > 80
                scope_is_partial = task_scope.get("scope") != "ALL_GUESTS"
                tasks_status = "PARTIAL" if (
                    scope_is_partial or excluded_task_rows or nodes_truncated
                    or tasks_truncated or "UNAVAILABLE" in task_states
                ) else "HEALTHY"
                if task_states and all(state == "UNAVAILABLE" for state in task_states):
                    tasks_status = "UNAVAILABLE"
        except (OSError, ValueError, UnicodeError, OverflowError) as exc:
            error_codes.append(_source_error_code(exc))

        states = (jobs_status, tasks_status)
        endpoint_status = "HEALTHY" if all(x == "HEALTHY" for x in states) else (
            "PARTIAL" if any(x in {"HEALTHY", "PARTIAL"} for x in states) else "UNAVAILABLE"
        )
        endpoints.append({
            "source_id": source_id,
            "status": endpoint_status,
            "jobs_status": jobs_status,
            "tasks_status": tasks_status,
            "task_scope": task_scope.get("scope", "UNKNOWN"),
            "visible_guest_count": (
                len(task_scope.get("guest_ids") or [])
                if task_scope.get("scope") in {"SELECTED_GUESTS", "PARTIAL"}
                and task_scope.get("all_guests") is not True else None
            ),
            "retrieved_at": _retrieved_at(),
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
            "jobs": jobs,
            "tasks": tasks[:80],
            "unattributed_tasks": unattributed_tasks[:80],
            "jobs_truncated": jobs_truncated,
            "tasks_truncated": tasks_truncated or nodes_truncated,
            "error_codes": sorted(set(error_codes)),
        })
    states = [row["status"] for row in endpoints]
    overall = "READABLE" if all(x == "HEALTHY" for x in states) else (
        "SOURCE_UNAVAILABLE" if all(x == "UNAVAILABLE" for x in states) else "PARTIAL"
    )
    report = {
        "status": overall,
        "source": "Proxmox vzdump jobs and archived tasks",
        "retrieved_at": _retrieved_at(),
        "coverage": "proxmox-vzdump-only",
        "endpoints": endpoints,
        "limitations": [
            "Does not verify backup contents, guest-application data, non-Proxmox backup systems, off-site custody, or restoreability.",
            "Task history is bounded to the latest 20 archived vzdump tasks per Proxmox node.",
            "Storage health is not checked by this read path.",
        ],
        "read_only": True,
    }
    report["formatted_summary"] = format_homelab_backup_status(report)
    return report


def format_homelab_backup_status(report: dict) -> str:
    """Compatibility wrapper for the pure backup response formatter."""
    return _format_homelab_backup_status(report, _bounded_text)


def _netbox_recent_inventory_updates(since: int) -> dict:
    """Read recent NetBox device/service timestamps without exposing change payloads."""
    device_url, device_token = supporting_source_specs()[0]
    configured = [("device", device_url, device_token), ("service", *netbox_services_spec())]
    configured = [(kind, url, token) for kind, url, token in configured if url]
    if not configured:
        return {
            "status": "NOT_CONFIGURED", "retrieved_at": None,
            "coverage": [], "objects": [], "truncated": False,
            "error_codes": [], "read_only": True,
        }

    since_text = datetime.fromtimestamp(since, timezone.utc).isoformat()
    objects = []
    endpoints = []
    for kind, endpoint, token_file in configured:
        started = time.monotonic()
        try:
            parsed = urlsplit(endpoint)
            if (
                parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
            ):
                raise ValueError("invalid NetBox inventory endpoint")
            query = urlencode({"limit": 100, "last_updated__gte": since_text})
            url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))
            payload = _fetch(url, token_file, timeout_seconds=8)
            rows = payload.get("results")
            count = payload.get("count")
            if (
                not isinstance(rows, list)
                or type(count) is not int or count < 0
            ):
                raise ValueError("NetBox inventory update response has an unsupported shape")
            invalid_rows = False
            for row in rows[:100]:
                if not isinstance(row, dict):
                    invalid_rows = True
                    continue
                raw_id = row.get("id")
                raw_name = row.get("name")
                raw_updated = row.get("last_updated")
                if (
                    isinstance(raw_id, bool)
                    or not isinstance(raw_id, (str, int))
                    or not re.fullmatch(r"[1-9][0-9]{0,19}", str(raw_id))
                    or not isinstance(raw_name, str)
                    or not isinstance(raw_updated, str)
                ):
                    invalid_rows = True
                    continue
                try:
                    updated = datetime.fromisoformat(raw_updated.replace("Z", "+00:00"))
                    if updated.tzinfo is None:
                        raise ValueError("NetBox update timestamp is not timezone-aware")
                    updated = updated.astimezone(timezone.utc)
                except (ValueError, OverflowError):
                    invalid_rows = True
                    continue
                if int(updated.timestamp()) < since:
                    continue
                name = _bounded_text(raw_name, 100)
                if not name:
                    invalid_rows = True
                    continue
                objects.append({
                    "object_type": kind,
                    "object_id": str(raw_id),
                    "name": name,
                    "last_updated": updated.isoformat(),
                })
            truncated = count > len(rows) or len(rows) > 100
            status = "PARTIAL" if truncated or invalid_rows else "HEALTHY"
            endpoints.append({
                "object_type": kind, "status": status,
                "retrieved_at": _retrieved_at(),
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "returned": min(len(rows), 100), "total": count,
                "truncated": truncated,
                "error_codes": [],
            })
        except (OSError, ValueError, UnicodeError, OverflowError) as exc:
            endpoints.append({
                "object_type": kind, "status": "UNAVAILABLE",
                "retrieved_at": _retrieved_at(),
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "returned": 0, "total": None, "truncated": False,
                "error_codes": [_source_error_code(exc)],
            })

    states = [row["status"] for row in endpoints]
    status = "READABLE" if all(state == "HEALTHY" for state in states) else (
        "SOURCE_UNAVAILABLE" if all(state == "UNAVAILABLE" for state in states)
        else "PARTIAL"
    )
    objects.sort(key=lambda row: row["last_updated"], reverse=True)
    truncated = any(row["truncated"] for row in endpoints) or len(objects) > 200
    return {
        "status": status,
        "retrieved_at": _retrieved_at(),
        "coverage": [row["object_type"] for row in endpoints],
        "endpoints": endpoints,
        "objects": objects[:200],
        "truncated": truncated,
        "error_codes": sorted({
            code for row in endpoints for code in row.get("error_codes", [])
        }),
        "read_only": True,
    }

def homelab_recent_activity(window_hours: int = 24) -> dict:
    """Read bounded Proxmox guest tasks and NetBox inventory timestamps."""
    from concurrent.futures import ThreadPoolExecutor

    if type(window_hours) is not int or not 1 <= window_hours <= 168:
        return {
            "status": "INVALID_REQUEST", "source": "homelab recent activity",
            "coverage": [], "endpoints": [], "netbox": {"status": "NOT_READ"},
            "read_only": True,
        }

    proxmox_configuration_error = False
    try:
        specs = proxmox_specs()
        token_ids = proxmox_token_ids() if specs else ()
        source_ids = proxmox_source_ids() if specs else ()
    except (OSError, ValueError):
        specs, token_ids, source_ids = (), (), ()
        proxmox_configuration_error = True

    ca_file = os.environ.get("HADES_PROXMOX_CA_FILE", "")
    since = int(time.time()) - window_hours * 60 * 60
    endpoints = []
    if proxmox_configuration_error:
        endpoints.append({
            "source_id": "proxmox", "status": "UNAVAILABLE",
            "scope": "UNKNOWN", "events": [],
            "error_codes": ["INVALID_PROXMOX_CONFIGURATION"],
        })
    for (resources_url, token_file), token_id, source_id in zip(
        specs, token_ids, source_ids, strict=True
    ):
        started = time.monotonic()
        parsed = urlsplit(resources_url)
        path = parsed.path.rstrip("/")
        suffix = "/cluster/resources"
        if (
            parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not path.endswith(suffix)
        ):
            endpoints.append({
                "source_id": source_id, "status": "UNAVAILABLE",
                "scope": "UNKNOWN", "events": [],
                "error_code": "INVALID_PROXMOX_RESOURCES_URL",
            })
            continue
        api_base = urlunsplit((parsed.scheme, parsed.netloc, path[:-len(suffix)], "", ""))
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                runtime_future = pool.submit(
                    _fetch, resources_url, token_file, ca_file, token_id,
                )
                permissions_future = pool.submit(
                    _fetch, _proxmox_permissions_url(resources_url),
                    token_file, ca_file, token_id,
                )
                runtime_payload = runtime_future.result()
                permissions_payload = permissions_future.result()
            runtime_rows = runtime_payload.get("data")
            if not isinstance(runtime_rows, list):
                raise ValueError("Proxmox runtime response has an unsupported shape")
            task_scope = _proxmox_guest_task_scope(permissions_payload)
            nodes = sorted({
                row.get("node") for row in runtime_rows
                if isinstance(row, dict) and row.get("type") == "node"
                and isinstance(row.get("node"), str)
                and re.fullmatch(r"[A-Za-z0-9._-]{1,128}", row["node"])
            })
            nodes_truncated = len(nodes) > 16
            nodes = nodes[:16]

            def read_node_tasks(node: str) -> tuple[str, list[dict], str | None, bool]:
                task_url = urljoin(
                    api_base.rstrip("/") + "/",
                    f"nodes/{quote(node, safe='')}/tasks?source=archive&limit=100&since={since}",
                )
                try:
                    payload = _fetch(task_url, token_file, ca_file, token_id)
                    rows = payload.get("data")
                    if not isinstance(rows, list):
                        raise ValueError("Proxmox task response has an unsupported shape")
                    normalized = []
                    for row in rows[:100]:
                        if not isinstance(row, dict):
                            continue
                        guest_id = row.get("id")
                        if not isinstance(guest_id, (str, int)):
                            continue
                        guest_id = str(guest_id)
                        if not re.fullmatch(r"[1-9][0-9]{0,19}", guest_id):
                            continue
                        if task_scope["all_guests"]:
                            if guest_id in task_scope["excluded_guest_ids"]:
                                continue
                        elif guest_id not in task_scope["guest_ids"]:
                            continue
                        started_at = row.get("starttime")
                        if (
                            not isinstance(started_at, (int, float))
                            or isinstance(started_at, bool) or started_at < since
                        ):
                            continue
                        task_type = row.get("type")
                        if not isinstance(task_type, str) or not re.fullmatch(
                            r"[A-Za-z][A-Za-z0-9_-]{0,31}", task_type,
                        ):
                            continue
                        task_type = task_type.casefold()
                        if not task_type.startswith(("qm", "vz")) and task_type != "vzdump":
                            continue
                        raw_status = str(row.get("status") or "").strip().upper()
                        status = "OK" if raw_status == "OK" else (
                            "RUNNING" if raw_status == "RUNNING" else
                            "ERROR" if raw_status.startswith("ERROR") else "UNKNOWN"
                        )
                        event = {
                            "source_id": source_id, "node": node,
                            "guest_id": guest_id, "task_type": task_type,
                            "status": status, "starttime": int(started_at),
                        }
                        ended_at = row.get("endtime")
                        if isinstance(ended_at, (int, float)) and not isinstance(ended_at, bool) and ended_at >= 0:
                            event["endtime"] = int(ended_at)
                        normalized.append(event)
                    return "HEALTHY", normalized, None, len(rows) >= 100
                except (OSError, ValueError, UnicodeError) as exc:
                    return "UNAVAILABLE", [], _source_error_code(exc), False

            with ThreadPoolExecutor(max_workers=min(8, max(1, len(nodes)))) as pool:
                task_results = list(pool.map(read_node_tasks, nodes))
            events = [event for _, rows, _, _ in task_results for event in rows]
            errors = sorted({error for _, _, error, _ in task_results if error})
            truncated = nodes_truncated or any(capped for _, _, _, capped in task_results)
            task_states = [state for state, _, _, _ in task_results]
            status = "HEALTHY"
            if not nodes or not task_states or all(state == "UNAVAILABLE" for state in task_states):
                status = "UNAVAILABLE"
            elif (
                "UNAVAILABLE" in task_states or truncated
                or task_scope["scope"] in {"PARTIAL", "SELECTED_GUESTS", "NO_GUEST_AUDIT"}
            ):
                status = "PARTIAL"
            events.sort(key=lambda row: row["starttime"], reverse=True)
            endpoints.append({
                "source_id": source_id, "status": status,
                "scope": task_scope["scope"], "retrieved_at": _retrieved_at(),
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "events": events[:200], "truncated": truncated or len(events) > 200,
                "error_codes": errors,
            })
        except (OSError, ValueError, UnicodeError, OverflowError) as exc:
            endpoints.append({
                "source_id": source_id, "status": "UNAVAILABLE",
                "scope": "UNKNOWN", "retrieved_at": _retrieved_at(),
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "events": [], "error_codes": [_source_error_code(exc)],
            })
    netbox = _netbox_recent_inventory_updates(since)
    proxmox_states = [endpoint["status"] for endpoint in endpoints]
    proxmox_status = "NOT_CONFIGURED" if not specs and not proxmox_configuration_error else (
        "READABLE" if proxmox_states and all(state == "HEALTHY" for state in proxmox_states)
        else "SOURCE_UNAVAILABLE" if proxmox_states and all(state == "UNAVAILABLE" for state in proxmox_states)
        else "PARTIAL"
    )
    source_statuses = [state for state in (proxmox_status, netbox["status"]) if state != "NOT_CONFIGURED"]
    if not source_statuses:
        status = "NOT_CONFIGURED"
    elif all(state == "READABLE" for state in source_statuses):
        status = "READABLE"
    elif all(state == "SOURCE_UNAVAILABLE" for state in source_statuses):
        status = "SOURCE_UNAVAILABLE"
    else:
        status = "PARTIAL"
    coverage = []
    if proxmox_status != "NOT_CONFIGURED":
        coverage.append("Proxmox archived guest tasks")
    if netbox["status"] != "NOT_CONFIGURED":
        coverage.extend(f"NetBox {kind} last_updated" for kind in netbox["coverage"])
    return {
        "status": status, "source": "Proxmox tasks and NetBox inventory updates",
        "source_status": {"proxmox": proxmox_status, "netbox": netbox["status"]},
        "retrieved_at": _retrieved_at(),
        "window_start": datetime.fromtimestamp(since, timezone.utc).isoformat(),
        "window_hours": window_hours,
        "coverage": coverage,
        "limitations": [
            "Proxmox activity is bounded to archived tasks for guests covered by each token's effective VM.Audit grants.",
            "NetBox updates show only current device/service records' last_updated timestamps; field diffs and deletions are not available.",
            "Host operating-system, package/driver, and in-guest service events are not included by these sources.",
            "This is bounded activity evidence, not a complete homelab change log or a saved before/after snapshot.",
            "Task completion does not prove the resulting guest configuration or application health.",
        ],
        "endpoints": endpoints, "netbox": netbox, "read_only": True,
    }

def format_homelab_recent_activity(report: dict) -> str:
    """Format bounded Proxmox and NetBox evidence without claiming complete history."""
    if not isinstance(report, dict) or not isinstance(report.get("endpoints"), list):
        return "I couldn't read recent homelab activity."
    status = str(report.get("status") or "UNKNOWN").upper()
    if status == "NOT_CONFIGURED":
        return "No recent Proxmox or NetBox activity source is configured, so I can't verify recent homelab changes."
    if status == "INVALID_REQUEST":
        return "Choose a recent activity window from 1 to 168 hours."
    if status in {"SOURCE_UNAVAILABLE", "CONFIGURATION_ERROR", "UNKNOWN"}:
        return "I couldn't read the configured Proxmox or NetBox activity sources, so recent homelab changes are unknown."
    events = [
        event for endpoint in report["endpoints"]
        if isinstance(endpoint, dict)
        for event in endpoint.get("events", [])
        if isinstance(event, dict)
    ]
    source_status = report.get("source_status") if isinstance(report.get("source_status"), dict) else {}
    proxmox_status = str(source_status.get("proxmox") or ("READABLE" if report.get("endpoints") else "NOT_CONFIGURED"))
    netbox = report.get("netbox") if isinstance(report.get("netbox"), dict) else {}
    netbox_status = str(source_status.get("netbox") or netbox.get("status") or "NOT_CONFIGURED")
    netbox_objects = netbox.get("objects") if isinstance(netbox.get("objects"), list) else []
    window_hours = report.get("window_hours")
    window = f"the last {window_hours} hours" if type(window_hours) is int and 1 <= window_hours <= 168 else "the requested time window"
    retrieved_at = _bounded_text(report.get("retrieved_at"), 40)
    read_stamp = f" Read at {retrieved_at}." if retrieved_at else " Read time unavailable."
    timeline = [(event.get("starttime", 0), "proxmox", event) for event in events]
    for obj in netbox_objects:
        if not isinstance(obj, dict):
            continue
        try:
            updated = datetime.fromisoformat(str(obj.get("last_updated", "")).replace("Z", "+00:00"))
            timestamp = updated.timestamp()
        except (ValueError, OverflowError):
            timestamp = 0
        timeline.append((timestamp, "netbox", obj))
    if timeline:
        summaries = []
        for _, source, item in sorted(timeline, key=lambda row: row[0], reverse=True)[:8]:
            if source == "netbox":
                kind = _bounded_text(item.get("object_type"), 24) or "inventory record"
                name = _bounded_text(item.get("name"), 100) or "an unnamed record"
                updated_at = _bounded_text(item.get("last_updated"), 40) or "time unavailable"
                summaries.append(f"NetBox {kind} {name} was last updated at {updated_at}")
                continue
            event = item
            guest = _bounded_text(event.get("guest_id"), 24) or "an audited guest"
            node = _bounded_text(event.get("node"), 64) or "a Proxmox node"
            task = _bounded_text(event.get("task_type"), 32) or "unknown task"
            state = str(event.get("status") or "UNKNOWN").casefold()
            summaries.append(f"{task} for guest {guest} on {node} ({state})")
        answer = "Recent recorded activity: " + "; ".join(summaries) + "."
        if len(timeline) > 8:
            answer += f" {len(timeline) - 8} additional records were omitted from this summary."
    else:
        empty = []
        if proxmox_status == "READABLE":
            empty.append("no archived Proxmox guest tasks were returned")
        elif proxmox_status == "PARTIAL":
            empty.append("no archived guest tasks were returned in the readable Proxmox scope")
        if netbox_status == "READABLE":
            empty.append("no recently updated NetBox device/service records were returned")
        answer = f"In {window}, " + " and ".join(empty) + "." if empty else "No configured activity source returned usable recent-change data."
    if proxmox_status in {"PARTIAL", "SOURCE_UNAVAILABLE", "NOT_CONFIGURED"}:
        detail = "not configured" if proxmox_status == "NOT_CONFIGURED" else "partial" if proxmox_status == "PARTIAL" else "unavailable"
        answer += f" Proxmox task coverage is {detail}."
    if netbox_status in {"PARTIAL", "SOURCE_UNAVAILABLE"}:
        detail = "partial" if netbox_status == "PARTIAL" else "unavailable"
        answer += f" NetBox inventory-update coverage is {detail}."
    elif netbox_status == "NOT_CONFIGURED":
        answer += " NetBox inventory-update reads are not configured."
    answer += read_stamp + (
        " This is bounded activity evidence, not a complete homelab change log. "
        "HADES has no saved prior snapshot for a before/after comparison; NetBox "
        "field differences and deletions are not included, and completed Proxmox "
        "tasks don't prove resulting guest configuration or application health. "
        "Host operating-system, package/driver, and in-guest service events aren't "
        "included in these sources."
    )
    return answer


def resolve_inference_node_labels(inventory: dict) -> dict[str, str]:
    """Resolve only linked NetBox device IDs needed to answer model-location queries."""
    from concurrent.futures import ThreadPoolExecutor

    base = os.environ.get("HADES_NETBOX_URL", "").rstrip("/")
    if not base or not isinstance(inventory, dict):
        return {}
    endpoints = inventory.get("endpoints") if isinstance(inventory.get("endpoints"), list) else []
    identities = sorted({
        endpoint.get("node_identity")
        for endpoint in endpoints
        if isinstance(endpoint, dict)
        and isinstance(endpoint.get("node_identity"), str)
        and re.fullmatch(r"netbox:device:[1-9][0-9]{0,19}", endpoint["node_identity"])
    })
    if not identities:
        return {}
    token_file = os.environ.get("HADES_NETBOX_TOKEN_FILE", "")

    def read(identity: str) -> tuple[str, str | None]:
        device_id = identity.rsplit(":", 1)[-1]
        try:
            document = _fetch(
                urljoin(f"{base}/", f"api/dcim/devices/{device_id}/"),
                token_file,
                timeout_seconds=4,
            )
        except Exception:
            return identity, None
        if (
            isinstance(document, dict)
            and str(document.get("id")) == device_id
            and isinstance(document.get("name"), str)
            and document["name"].strip()
        ):
            return identity, _bounded_text(document["name"], 100)
        return identity, None

    with ThreadPoolExecutor(max_workers=min(8, len(identities))) as pool:
        return {identity: name for identity, name in pool.map(read, identities) if name}

def homelab_owner_snapshot() -> dict:
    """Compose the two read-only owner views without cross-authority inference."""
    summary = homelab_summary()
    compute = homelab_compute_capabilities()
    return {
        "status": "OK" if summary.get("status") == "OK" and compute.get("status") == "OK" else "PARTIAL",
        "summary": summary,
        "compute": compute,
        "answer_contract": {
            "online_source": "summary.online_names from Proxmox runtime only",
            "gpu_source": "compute.machines from observed capability matrix",
            "inventory_is_not_liveness": True,
            "writes_performed": False,
        },
        "read_only": True,
    }


async def list_tools():
    return ListToolsResult(tools=TOOLS)


async def call_tool(name, arguments):
    if name == "homelab_recent_activity":
        args = arguments or {}
        result = homelab_recent_activity(args.get("window_hours", 24))
    elif name == "homelab_backup_status":
        result = homelab_backup_status()
    elif name == "homelab_owner_snapshot":
        result = homelab_owner_snapshot()
    elif name == "homelab_discovery_scan":
        args = arguments or {}
        target = args.get("target")
        if not isinstance(target, str) or not target.strip():
            raise ValueError("discovery scan target is required")
        allowed = [value.strip() for value in os.environ.get("HADES_DISCOVERY_ALLOWED_NETWORKS", "").split(",") if value.strip()]
        if not allowed:
            raise ValueError("HADES_DISCOVERY_ALLOWED_NETWORKS is not configured")
        ports = args.get("ports", DEFAULT_PORTS)
        if not isinstance(ports, str):
            raise ValueError("discovery scan ports must be a string")
        result = await anyio.to_thread.run_sync(
            lambda: run_bounded_scan(target, allowed_networks=allowed, ports=ports)
        )
    elif name == "homelab_discovery_candidates":
        args = arguments or {}
        evidence = args.get("evidence")
        netbox = args.get("netbox")
        encoded = json.dumps(evidence, separators=(",", ":")).encode() if isinstance(evidence, dict) else b""
        if len(encoded) > MAX_RESPONSE_BYTES:
            raise ValueError("discovery evidence exceeds bounded size")
        result = propose_inventory_candidates(evidence, netbox)
    elif name == "homelab_compute_capabilities":
        result = homelab_compute_capabilities()
    elif name == "homelab_inference_inventory":
        result = homelab_inference_inventory()
    elif name == "homelab_inference_capacity":
        result = homelab_inference_capacity()
    elif name == "homelab_gpu_telemetry":
        result = homelab_gpu_telemetry()
    elif name == "homelab_summary":
        result = homelab_summary()
    else:
        raise ValueError(f"unknown tool: {name}")
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, sort_keys=True))])


async def _list_tools(_context, _params):
    return await list_tools()


async def _call_tool(_context, params):
    return await call_tool(params.name, params.arguments)


async def main():
    server = Server("hades-homelab-readonly", on_list_tools=_list_tools, on_call_tool=_call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
