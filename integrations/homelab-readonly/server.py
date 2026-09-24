"""Read-only MCP composition adapter for approved homelab endpoints."""

from __future__ import annotations

import json
import os
import ssl
from pathlib import Path
from urllib.request import Request, urlopen

import anyio
import yaml
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from reconcile import summarize
from catalog import propose_inventory_candidates
from scan import DEFAULT_PORTS, run_bounded_scan
from config import proxmox_specs, proxmox_token_ids, source_specs


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TOKEN_BYTES = 8192
TIMEOUT_SECONDS = 10
TOOLS = [Tool(
    name="homelab_summary",
    description=(
        "MANDATORY for any owner question about servers, hosts, VMs, online "
        "status, or homelab infrastructure: call this tool first. Read "
        "approved Proxmox runtime, NetBox intended inventory, and Uptime "
        "Kuma observed availability, plus clearly labeled supplemental "
        "hardware inventory. Only Proxmox runtime_status=online for "
        "hosts or running for guests means currently live; NetBox-only "
        "inventory is not liveness. Explain "
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


def _fetch(url: str, token_file: str = "", ca_file: str = "", proxmox_token_id: str = "") -> dict:
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
    with urlopen(request, timeout=TIMEOUT_SECONDS, context=context) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
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
            monitors.append({
                "name": monitor["name"],
                "status": status,
                "last_updated": latest.get("time"),
            })
    return {"monitors": monitors}


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
    proxmox_value: dict | None = None
    try:
        rows: list[dict] = []
        ca_file = os.environ.get("HADES_PROXMOX_CA_FILE", "")
        token_ids = proxmox_token_ids()
        for index, (url, token_file) in enumerate(proxmox_specs()):
            if not url:
                continue
            result = _fetch(url, token_file, ca_file, token_ids[index])
            rows.extend(row for row in result.get("data", []) if isinstance(row, dict))
        if rows or proxmox_specs():
            proxmox_value = {"data": rows}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    values.append(proxmox_value)
    for label, (url, token_file) in zip(("NetBox", "Uptime Kuma"), source_specs()[1:], strict=True):
        if not url:
            values.append(None)
            errors.append(f"{label} source is not configured")
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
            values.append(_normalize_kuma_status(value) if label == "Uptime Kuma" else value)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            values.append(None)
            errors.append(str(exc))
    result = summarize(*values)
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
            "runtime_status": resource.get("runtime_status"),
            "currently_online": resource.get("currently_online"),
            "runtime": resource.get("runtime"),
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


def homelab_compute_capabilities() -> dict:
    """Return observed hardware facts without claiming live availability."""
    from config import capability_matrix_file

    path_value = capability_matrix_file()
    if not path_value:
        return {
            "status": "UNAVAILABLE",
            "source": "observed capability matrix",
            "error": "capability matrix is not configured",
            "read_only": True,
        }
    path = Path(path_value)
    if not path.is_file() or path.is_symlink():
        return {
            "status": "UNAVAILABLE",
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
    if name == "homelab_owner_snapshot":
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
