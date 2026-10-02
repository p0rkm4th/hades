"""Read-only MCP composition adapter for approved homelab endpoints."""

from __future__ import annotations

import json
import os
import re
import ssl
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlsplit

import anyio
import yaml
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from reconcile import _freshness, summarize
from catalog import propose_inventory_candidates
from scan import DEFAULT_PORTS, run_bounded_scan
from config import (
    identity_links_file,
    load_identity_links,
    netbox_services_spec,
    proxmox_source_ids,
    proxmox_specs,
    proxmox_token_ids,
    source_specs,
)


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TOKEN_BYTES = 8192
TIMEOUT_SECONDS = 10


def _nonnegative_int(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _bounded_text(value: object, limit: int = 256) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join("".join(char if char.isprintable() else " " for char in value).split())
    return normalized[:limit] or None
TOOLS = [Tool(
    name="homelab_summary",
    description=(
        "MANDATORY for any owner question about servers, hosts, VMs, online "
        "status, application-service endpoints, ports, or homelab infrastructure: "
        "call this tool first. Read approved Proxmox runtime, NetBox intended "
        "device and application-service inventory, and Uptime Kuma observed "
        "availability, plus clearly labeled supplemental "
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
    name="homelab_inference_inventory",
    description=(
        "Read configured read-only Ollama or OpenAI-compatible inference endpoints. "
        "Query provider model catalogs and Ollama loaded-model state; keep endpoint "
        "identity, freshness, and partial failures explicit. This does not infer free "
        "GPU capacity or model fit; catalog checks do not prove generation "
        "works, and this tool cannot mutate providers."
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


def _fetch(
    url: str,
    token_file: str = "",
    ca_file: str = "",
    proxmox_token_id: str = "",
    timeout_seconds: int = TIMEOUT_SECONDS,
) -> dict:
    if not url:
        raise ValueError("homelab source is not configured")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("homelab source must use HTTP(S)")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("homelab source URL must not contain credentials or a fragment")
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
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("homelab response exceeds bounded size")
    result = json.loads(body)
    if not isinstance(result, dict):
        raise ValueError("homelab response must be a JSON object")
    return result


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


def _retrieved_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_result(
    name: str,
    status: str,
    started: float,
    *,
    rows: int | None = None,
    error_code: str | None = None,
) -> dict:
    result = {
        "source": name,
        "status": status,
        "observation_scope": "source_read",
        "retrieved_at": _retrieved_at(),
        "duration_ms": round((time.monotonic() - started) * 1000, 1),
    }
    if rows is not None:
        result["rows"] = rows
    if error_code:
        result["error_code"] = error_code
    return result


def _proxmox_identity(row: dict, endpoint_id: str, index: int) -> str:
    kind = str(row.get("type") or "resource")
    if kind == "node" and row.get("node"):
        object_id = str(row["node"])
    elif kind in {"qemu", "lxc"} and row.get("vmid") is not None:
        object_id = str(row["vmid"])
    elif row.get("id") is not None:
        object_id = str(row["id"])
    else:
        object_id = f"row-{index}"
    return f"proxmox:{endpoint_id}:{kind}:{object_id}"


def _read_proxmox_endpoint(args: tuple[int, str, str, str, str, str]) -> dict:
    """Read one independent Proxmox endpoint without serializing the cluster."""
    index, url, token_file, token_id, source_id, ca_file = args
    source_name = f"Proxmox[{index + 1}]"
    started = time.monotonic()
    if not url:
        return {
            "rows": [],
            "source": _source_result(source_name, "NOT_CONFIGURED", started),
        }
    try:
        result = _fetch(url, token_file, ca_file, token_id)
        rows = []
        for row_index, row in enumerate(result.get("data", [])):
            if not isinstance(row, dict):
                continue
            source_row = dict(row)
            source_row["_hades_identity"] = _proxmox_identity(
                source_row, source_id, row_index,
            )
            rows.append(source_row)
        return {
            "rows": rows,
            "source": _source_result(source_name, "HEALTHY", started, rows=len(rows)),
        }
    except (OSError, ValueError, UnicodeError) as exc:
        return {
            "rows": [],
            "source": _source_result(
                source_name, "UNAVAILABLE", started,
                error_code=_source_error_code(exc),
            ),
            "error": f"{source_name} unavailable",
        }


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
                "id": monitor.get("id"),
                "name": monitor["name"],
                "status": status,
                "last_updated": latest.get("time"),
                "monitor_type": monitor.get("type"),
            }
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
    source_results: list[dict] = []
    proxmox_value: dict | None = None
    netbox_value: dict | None = None
    rows: list[dict] = []
    proxmox_specs_value = ()
    token_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    source_id_error: str | None = None
    try:
        proxmox_specs_value = proxmox_specs()
        token_ids = proxmox_token_ids()
    except (OSError, ValueError) as exc:
        proxmox_specs_value = ()
        started = time.monotonic()
        source_results.append(_source_result(
            "Proxmox configuration", "UNAVAILABLE", started,
            error_code=_source_error_code(exc),
        ))
        errors.append("Proxmox configuration unavailable")
    try:
        source_ids = proxmox_source_ids(proxmox_specs_value)
    except ValueError:
        # An invalid display/identity alias must not suppress otherwise valid
        # read-only Proxmox data. Ordinal labels stay local and cannot be
        # cross-source linked without configured stable IDs.
        source_ids = tuple(f"endpoint-{index + 1}" for index in range(len(proxmox_specs_value)))
        source_id_error = "Proxmox source identity configuration unavailable"
    ca_file = os.environ.get("HADES_PROXMOX_CA_FILE", "")
    successful_proxmox_sources = 0
    failed_proxmox_sources = 0
    from concurrent.futures import ThreadPoolExecutor

    proxmox_requests = [
        (index, url, token_file, token_ids[index], source_ids[index], ca_file)
        for index, (url, token_file) in enumerate(proxmox_specs_value)
    ]
    if len(proxmox_requests) > 1:
        with ThreadPoolExecutor(max_workers=min(8, len(proxmox_requests))) as pool:
            proxmox_results = list(pool.map(_read_proxmox_endpoint, proxmox_requests))
    else:
        proxmox_results = [_read_proxmox_endpoint(args) for args in proxmox_requests]
    for item in proxmox_results:
        rows.extend(item["rows"])
        source_results.append(item["source"])
        if item["source"]["status"] == "HEALTHY":
            successful_proxmox_sources += 1
        elif item["source"]["status"] == "UNAVAILABLE":
            failed_proxmox_sources += 1
            errors.append(item["error"])
    if successful_proxmox_sources:
        proxmox_value = {"data": rows}
    if failed_proxmox_sources and successful_proxmox_sources:
        source_results.append({
            "source": "Proxmox",
            "status": "DEGRADED",
            "observation_scope": "source_read_aggregate",
            "available_endpoints": successful_proxmox_sources,
            "unavailable_endpoints": failed_proxmox_sources,
        })
    elif successful_proxmox_sources and not failed_proxmox_sources:
        source_results.append({
            "source": "Proxmox",
            "status": "HEALTHY",
            "observation_scope": "source_read_aggregate",
            "available_endpoints": successful_proxmox_sources,
            "unavailable_endpoints": 0,
        })
    elif not proxmox_specs_value and not any(
        row.get("source") == "Proxmox configuration" for row in source_results
    ):
        source_results.append({
            "source": "Proxmox", "status": "NOT_CONFIGURED",
            "observation_scope": "source_read_aggregate",
        })
    values.append(proxmox_value)
    for label, (url, token_file) in zip(("NetBox", "Uptime Kuma"), source_specs()[1:], strict=True):
        started = time.monotonic()
        if not url:
            values.append(None)
            source_results.append(_source_result(label, "NOT_CONFIGURED", started))
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
            normalized = _normalize_kuma_status(value) if label == "Uptime Kuma" else value
            values.append(normalized)
            count = len(normalized.get("monitors", [])) if label == "Uptime Kuma" else len(normalized.get("results", []))
            source_results.append(_source_result(label, "HEALTHY", started, rows=count))
            if label == "NetBox":
                netbox_value = value
        except (OSError, ValueError, UnicodeError) as exc:
            values.append(None)
            source_results.append(_source_result(
                label, "UNAVAILABLE", started,
                error_code=_source_error_code(exc),
            ))
            errors.append(f"{label} unavailable")
    identity_links: dict[str, str] = {}
    identity_links_configured = bool(identity_links_file())
    try:
        identity_links = load_identity_links()
        has_proxmox_links = any(key.startswith("proxmox:") for key in identity_links)
        if has_proxmox_links and (source_id_error or (
            len(proxmox_specs_value) > 1
            and not os.environ.get("HADES_PROXMOX_SOURCE_IDS", "").strip()
        )):
            identity_links = {
                key: value for key, value in identity_links.items()
                if not key.startswith("proxmox:")
            }
            source_id_error = "Stable Proxmox source IDs are required for configured identity links"
        source_results.append({
            "source": "Homelab identity links",
            "status": "HEALTHY" if identity_links_configured else "NOT_CONFIGURED",
            "observation_scope": "source_read",
            "rows": len(identity_links),
        })
    except (OSError, ValueError, UnicodeError) as exc:
        source_results.append(_source_result(
            "Homelab identity links", "UNAVAILABLE", time.monotonic(),
            error_code=_source_error_code(exc),
        ))
        errors.append("Homelab identity links unavailable")
    if source_id_error:
        errors.append(source_id_error)
        source_results.append({
            "source": "Proxmox source identities",
            "status": "UNAVAILABLE",
            "observation_scope": "source_configuration",
        })
    result = summarize(*values, identity_links=identity_links)
    from services import project_netbox_services

    service_url, service_token_file = netbox_services_spec()
    if service_url:
        started = time.monotonic()
        try:
            service_payload = _fetch(service_url, service_token_file)
            result["service_catalog"] = project_netbox_services(
                service_payload, netbox_value
            )
            source_results.append(_source_result(
                "NetBox application services", "HEALTHY", started,
                rows=len(result["service_catalog"].get("services", [])),
            ))
        except (OSError, ValueError, UnicodeError) as exc:
            result["service_catalog"] = {
                "status": "UNAVAILABLE",
                "source": "NetBox application services",
                "coverage": "UNKNOWN",
                "records_returned": 0,
                "source_total": None,
                "services": [],
                "inventory_is_not_liveness": True,
                "writes_performed": False,
                "limitation": "NetBox application-service inventory could not be read.",
            }
            source_results.append(_source_result(
                "NetBox application services", "UNAVAILABLE", started,
                error_code=_source_error_code(exc),
            ))
            errors.append("NetBox application services unavailable")
    else:
        result["service_catalog"] = {
            "status": "NOT_CONFIGURED",
            "source": "NetBox application services",
            "coverage": "UNKNOWN",
            "records_returned": 0,
            "source_total": None,
            "services": [],
            "inventory_is_not_liveness": True,
            "writes_performed": False,
            "limitation": "NetBox application-service endpoint is not configured.",
        }
        source_results.append({
            "source": "NetBox application services", "status": "NOT_CONFIGURED",
            "observation_scope": "source_read",
        })
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
            "inventory": resource.get("inventory"),
            "primary_ip": inventory.get("primary_ip"),
            "role": inventory.get("role"),
            "availability": resource.get("availability"),
            "availability_observations": resource.get("availability_observations", []),
            "availability_status": availability.get("status"),
            "availability_freshness": resource.get("availability_freshness"),
            "conflicts": resource.get("conflicts", []),
        })
    # Keep the detailed index useful for location questions without allowing a
    # large inventory to dominate the model context. The complete online and
    # inventory-only name lists above remain authoritative; this is only the
    # optional per-resource detail view.
    # A broad homelab snapshot is currently bounded by the source row caps
    # above (32 total records). Returning four alphabetically first entries
    # silently omitted most hosts and monitor results from owner follow-ups.
    resource_limit = 64
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
        result["status"] = "PARTIAL"
    result["sources"] = source_results
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
    observed_at = document.get("observed_at")
    freshness = _freshness(
        observed_at,
        now=datetime.now(timezone.utc),
        max_age=timedelta(days=7),
    )
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
        "status": "OK" if freshness == "FRESH" else freshness,
        "source": "tracked observed capability matrix",
        "availability_not_provided": True,
        "observed_at": observed_at,
        "freshness": freshness,
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


def _inference_endpoint_read(endpoint: dict[str, str], links: dict[str, str]) -> dict:
    source_id = endpoint["id"]
    provider = endpoint.get("provider", "ollama")
    source_identity = f"inference:{source_id}"
    node_identity = links.get(source_identity)
    base = endpoint["url"].rstrip("/") + "/"
    started = time.monotonic()
    checked_at = _retrieved_at()
    try:
        if provider == "openai-compatible":
            catalog = _fetch(
                urljoin(base, "v1/models"), endpoint["token_file"], endpoint["ca_file"],
                timeout_seconds=4,
            ).get("data")
            if not isinstance(catalog, list) or len(catalog) > 512:
                raise ValueError("inference model catalog has an invalid shape")
            tags = [{"name": item.get("id")} for item in catalog if isinstance(item, dict)]
        else:
            tags = _fetch(
                urljoin(base, "api/tags"), endpoint["token_file"], endpoint["ca_file"],
                timeout_seconds=4,
            ).get("models")
            if not isinstance(tags, list) or len(tags) > 512:
                raise ValueError("inference model catalog has an invalid shape")
    except Exception as exc:
        return {
            "source_identity": source_identity,
            "provider": provider,
            "node_identity": node_identity,
            "identity_status": "LINKED" if node_identity else "UNLINKED",
            "status": "SOURCE_UNAVAILABLE",
            "loaded_status": "UNKNOWN",
            "checked_at": checked_at,
            "health_scope": "provider catalog request unavailable; no generation request was made",
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
            "error": _source_error_code(exc),
            "models": [],
            "read_only": True,
        }
    models = []
    for item in tags:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        model_name = _bounded_text(item["name"])
        if not model_name:
            continue
        details = item.get("details") if isinstance(item.get("details"), dict) else {}
        model = {
            "name": model_name,
            "modified_at": _bounded_text(item.get("modified_at"), 64),
            "size_bytes": _nonnegative_int(item.get("size")),
            "digest": _bounded_text(item.get("digest"), 128),
            "family": _bounded_text(details.get("family"), 128),
            "parameter_size": _bounded_text(details.get("parameter_size"), 64),
            "quantization_level": _bounded_text(details.get("quantization_level"), 64),
        }
        models.append(model)
    loaded = []
    if provider == "ollama":
        try:
            running = _fetch(
                urljoin(base, "api/ps"), endpoint["token_file"], endpoint["ca_file"],
                timeout_seconds=4,
            ).get("models")
            if not isinstance(running, list) or len(running) > 512:
                raise ValueError("inference loaded-model response has an invalid shape")
            for item in running:
                if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                    continue
                model_name = _bounded_text(item["name"])
                if not model_name:
                    continue
                loaded.append({
                    "name": model_name,
                    "size_bytes": _nonnegative_int(item.get("size")),
                    "size_vram_bytes": _nonnegative_int(item.get("size_vram")),
                    "expires_at": _bounded_text(item.get("expires_at"), 64),
                })
            loaded_status = "CURRENT"
        except Exception as exc:
            loaded_status = _source_error_code(exc)
    else:
        # OpenAI-compatible model catalogs do not standardize residency.
        loaded_status = "UNSUPPORTED"
    return {
        "source_identity": source_identity,
        "provider": provider,
        "node_identity": node_identity,
        "identity_status": "LINKED" if node_identity else "UNLINKED",
        "status": "READABLE" if loaded_status in {"CURRENT", "UNSUPPORTED"} else "PARTIAL",
        "checked_at": checked_at,
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "health_scope": (
            "provider model catalog and residency APIs only; no generation request was made"
            if provider == "ollama" else
            "OpenAI-compatible model catalog only; residency and generation were not checked"
        ),
        "catalog_freshness": "LIVE",
        "loaded_status": loaded_status,
        "loaded_models": loaded,
        "models": models,
        "read_only": True,
    }


def homelab_inference_inventory() -> dict:
    """Query supported provider model catalogs and available residency read-only."""
    from concurrent.futures import ThreadPoolExecutor
    from config import inference_endpoint_specs, load_identity_links

    try:
        endpoints = inference_endpoint_specs()
        links = load_identity_links()
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "status": "CONFIGURATION_ERROR",
            "endpoints": [],
            "error": "inference source configuration is invalid",
            "read_only": True,
        }
    if not endpoints:
        return {
            "status": "NOT_CONFIGURED",
            "source": "configured provider-native inference APIs",
            "endpoints": [],
            "read_only": True,
        }
    with ThreadPoolExecutor(max_workers=min(8, len(endpoints))) as pool:
        results = list(pool.map(lambda endpoint: _inference_endpoint_read(endpoint, links), endpoints))
    states = [row["status"] for row in results]
    status = "READABLE" if all(value == "READABLE" for value in states) else (
        "SOURCE_UNAVAILABLE" if all(value == "SOURCE_UNAVAILABLE" for value in states)
        else "PARTIAL"
    )
    return {
        "status": status,
        "source": "configured provider-native inference APIs",
        "retrieved_at": _retrieved_at(),
        "endpoints": results,
        "read_only": True,
    }


def _format_node_activity_fallback(user_text: str, summary: dict | None) -> str:
    """Use runtime/inventory evidence when the named machine has no provider link."""
    match = re.search(
        r"\bwhat(?:['’]s|s|\s+is)\s+(?P<target>[a-z0-9][a-z0-9 ._'’-]{0,60}?)\s+"
        r"(?:doing|running)\b",
        str(user_text or ""), re.IGNORECASE,
    )
    target = re.sub(r"[^a-z0-9]+", "", match.group("target").casefold()) if match else ""
    resources = summary.get("resources", []) if isinstance(summary, dict) else []
    matches = []
    for resource in resources if isinstance(resources, list) else []:
        if not isinstance(resource, dict):
            continue
        inventory = resource.get("inventory") if isinstance(resource.get("inventory"), dict) else {}
        label = inventory.get("name") or resource.get("name")
        if target and re.sub(r"[^a-z0-9]+", "", str(label or "").casefold()) == target:
            matches.append((resource, inventory, str(label)))
    if len(matches) > 1:
        return "I found multiple inventory records matching that machine, so I can't choose one current status safely."
    if not matches:
        return "I can't match that machine to a current runtime record or linked inference endpoint, so its activity is unknown."
    resource, inventory, label = matches[0]
    runtime_status = str(resource.get("runtime_status") or "UNKNOWN").casefold()
    if runtime_status in {"online", "running"}:
        response = f"Proxmox currently reports {label} {runtime_status}."
    elif runtime_status in {"offline", "stopped"}:
        response = f"Proxmox currently reports {label} {runtime_status}."
    else:
        response = f"I don't have a current Proxmox runtime check for {label}, so I can't say whether it's online."
    role = inventory.get("role")
    if isinstance(role, str) and role.strip():
        response += f" NetBox lists its role as {role.strip()[:120]}."
    conflicts = resource.get("conflicts") if isinstance(resource.get("conflicts"), list) else []
    if conflicts:
        details = [" ".join(str(value).split())[:160] for value in conflicts[:4] if value]
        if details:
            response += " Source disagreement: " + "; ".join(details) + "."
    return response + " No linked inference endpoint provides current model activity for this machine."


def format_inference_inventory_response(user_text: str, inventory: dict, summary: dict) -> str:
    """Present bounded current model inventory without overstating health or fit."""
    node_activity = re.search(
        r"\bwhat(?:['’]s|s|\s+is)\s+(?P<target>[a-z0-9][a-z0-9 ._'’-]{0,60}?)\s+"
        r"(?:doing|running)\b",
        str(user_text or ""), re.IGNORECASE,
    )
    if not isinstance(inventory, dict):
        if node_activity:
            return _format_node_activity_fallback(user_text, summary)
        return "I couldn't read the configured inference inventory, so I can't verify model availability right now."
    status = str(inventory.get("status") or "UNKNOWN")
    endpoints = inventory.get("endpoints") if isinstance(inventory.get("endpoints"), list) else []
    if status == "NOT_CONFIGURED":
        if node_activity:
            return _format_node_activity_fallback(user_text, summary)
        return "Provider-native model inventory is not configured here, so I can't verify which models are installed or loaded."
    if not endpoints:
        if node_activity:
            return _format_node_activity_fallback(user_text, summary)
        return "I couldn't read any configured model endpoints, so I can't verify model availability right now."

    gpu_availability_intent = bool(re.search(
        r"\b(?:which|what)\b.{0,35}\b(?:gpus?|graphics cards?)\b.{0,35}\b(?:free|available|capacity|memory|room|load|utili[sz]ation)\b",
        str(user_text or ""), re.IGNORECASE,
    ))
    placement_intent = bool(re.search(
        r"\bwhere\s+should\s+i\s+(?:run|host|put)\b|"
        r"\b(?:what|which)\s+(?:machine|server|gpu)\b.{0,35}\b(?:should|can|has room|have room)\b.{0,45}\b(?:model|workload)\b|"
        r"\b(?:can|could)\b.{0,60}\b(?:handle|fit|run|host)\b.{0,35}\b(?:another|new|\d+\s*(?:gb|b)|model|workload)\b",
        str(user_text or ""), re.IGNORECASE,
    ))
    if gpu_availability_intent:
        return (
            "I can't verify which GPUs are free right now. Live GPU utilization and free-VRAM "
            "telemetry are not connected. A hardware inventory or empty model-residency "
            "report does not establish available capacity."
        )

    resource_names = {}
    for resource in (summary.get("resources", []) if isinstance(summary, dict) else []):
        if not isinstance(resource, dict):
            continue
        identity = resource.get("identity")
        inventory_record = resource.get("inventory")
        if isinstance(identity, dict) and isinstance(inventory_record, dict):
            canonical = identity.get("canonical_id")
            if canonical:
                resource_names[canonical] = inventory_record.get("name") or resource.get("name")

    if node_activity:
        requested_node = re.sub(r"[^a-z0-9]+", "", node_activity.group("target").casefold())
        matching_nodes = [
            (identity, label) for identity, label in resource_names.items()
            if isinstance(label, str)
            and re.sub(r"[^a-z0-9]+", "", label.casefold()) == requested_node
        ]
        if len(matching_nodes) != 1:
            return _format_node_activity_fallback(user_text, summary)
        node_identity, label = matching_nodes[0]
        linked = [
            endpoint for endpoint in endpoints[:16]
            if isinstance(endpoint, dict) and endpoint.get("node_identity") == node_identity
        ]
        if len(linked) != 1:
            return _format_node_activity_fallback(user_text, summary)
        endpoint = linked[0]
        if endpoint.get("status") != "READABLE":
            return f"The inference endpoint linked to {label} is not responding to its catalog read, so I can't verify its model activity."
        models = endpoint.get("models") if isinstance(endpoint.get("models"), list) else []
        loaded = endpoint.get("loaded_models") if isinstance(endpoint.get("loaded_models"), list) else []
        names = list(dict.fromkeys(
            str(model.get("name")) for model in models
            if isinstance(model, dict) and model.get("name")
        ))[:10]
        result = f"The inference endpoint linked to {label} is responding."
        result += " Provider catalog lists " + (", ".join(names) if names else "no installed models") + "."
        if endpoint.get("loaded_status") == "CURRENT":
            loaded_names = list(dict.fromkeys(
                str(model.get("name")) for model in loaded
                if isinstance(model, dict) and model.get("name")
            ))[:8]
            result += " Currently loaded: " + (", ".join(loaded_names) if loaded_names else "none reported") + "."
        else:
            result += " Current loaded-model state is unavailable."
        return result + " This does not establish host CPU/GPU utilization or prove a generation request works."

    if placement_intent:
        candidates = []
        capability_machines = (
            summary.get("capability_machines", []) if isinstance(summary, dict) else []
        )
        capabilities = {
            re.sub(r"[^a-z0-9]+", "", str(machine.get("name") or "").casefold()): machine
            for machine in capability_machines if isinstance(machine, dict)
        }
        for endpoint in endpoints[:16]:
            if not isinstance(endpoint, dict) or endpoint.get("status") != "READABLE":
                continue
            label = resource_names.get(endpoint.get("node_identity"))
            if not isinstance(label, str) or not label:
                continue
            key = re.sub(r"[^a-z0-9]+", "", label.casefold())
            machine = capabilities.get(key, {})
            role = " ".join(str(machine.get("role") or "").split())[:120]
            loaded = endpoint.get("loaded_models") if isinstance(endpoint.get("loaded_models"), list) else []
            loaded_state = endpoint.get("loaded_status")
            gpu_rows = machine.get("gpus") if isinstance(machine.get("gpus"), list) else []
            gpu_names = []
            for gpu in gpu_rows:
                if isinstance(gpu, str):
                    gpu_names.append(gpu)
                elif isinstance(gpu, dict) and (gpu.get("model") or gpu.get("name")):
                    count = gpu.get("count")
                    prefix = f"{count} × " if isinstance(count, int) and 1 < count < 129 else ""
                    gpu_names.append(prefix + str(gpu.get("model") or gpu.get("name")))
            candidates.append((
                label, role, gpu_names[:5], str(summary.get("capability_freshness") or "UNKNOWN").upper(),
                loaded, loaded_state,
            ))
        if not candidates:
            return (
                "I can't recommend an inference host from the current reads: no responding "
                "provider endpoint is linked to a named inventory device."
            )
        candidates.sort(key=lambda row: (not any(term in row[1].casefold() for term in ("deep", "large", "inference", "gpu")), row[0].casefold()))
        label, role, gpu_names, hardware_freshness, loaded, loaded_state = candidates[0]
        reason = f"{label} is a candidate to evaluate because its linked inference endpoint is responding"
        if role:
            reason += f" and its recorded role is {role}"
        if gpu_names:
            reason += "; hardware inventory lists " + ", ".join(gpu_names)
            reason += f" ({hardware_freshness.casefold()} observation)"
        if loaded_state == "CURRENT":
            names = [str(model.get("name")) for model in loaded if isinstance(model, dict) and model.get("name")]
            reason += "; provider reports " + ("no models currently loaded" if not names else "these models loaded: " + ", ".join(names[:5]))
        reason += "."
        if len(candidates) > 1:
            reason += " Other responding linked endpoints may also be candidates depending on model size and workload."
        return (
            reason + " This is a shortlist only: live GPU load/free VRAM and the model's "
            "runtime memory needs, including quantization and context, are not available, "
            "so I can't confirm capacity or fit."
        )

    reachable = []
    all_models = []
    all_loaded = []
    loaded_unknown_labels = set()
    unavailable = 0
    for endpoint in endpoints[:16]:
        if not isinstance(endpoint, dict):
            continue
        endpoint_id = str(endpoint.get("source_identity") or "configured provider")
        machine = resource_names.get(endpoint.get("node_identity"))
        label = str(machine or endpoint_id)
        if endpoint.get("status") == "SOURCE_UNAVAILABLE":
            unavailable += 1
            continue
        reachable.append(label)
        models = endpoint.get("models") if isinstance(endpoint.get("models"), list) else []
        loaded = endpoint.get("loaded_models") if isinstance(endpoint.get("loaded_models"), list) else []
        all_models.extend((label, model) for model in models if isinstance(model, dict))
        if endpoint.get("loaded_status") == "CURRENT":
            all_loaded.extend((label, model) for model in loaded if isinstance(model, dict))
        elif models:
            loaded_unknown_labels.add(label)

    where_match = re.search(
        r"\bwhere(?:['’]s|\s+is)\s+([a-z0-9._-]+(?::[a-z0-9._-]+)?(?:\s+\d+(?:\.\d+)?b)?)\b",
        str(user_text or ""), re.IGNORECASE,
    )
    if where_match:
        requested = where_match.group(1).strip()[:128].casefold()
        matches = [
            (label, model) for label, model in all_models
            if requested in str(model.get("name") or "").casefold()
        ]
        if matches:
            locations = sorted({label for label, _model in matches})
            names = sorted({str(model.get("name")) for _label, model in matches})
            target_names = {name.casefold() for name in names}
            loaded_locations = sorted({
                label for label, model in all_loaded
                if str(model.get("name") or "").casefold() in target_names
            })
            result = f"{', '.join(names[:3])} is listed by {', '.join(locations[:4])}."
            if loaded_locations:
                result += f" Loaded now on {', '.join(loaded_locations[:4])}."
            elif any(label in loaded_unknown_labels for label in locations):
                result += " Current loaded-model state is unavailable for at least one matching provider."
            else:
                result += " It is not currently reported as loaded."
            return result + " This checks the provider catalog and residency APIs, not a generation request."
        if not reachable:
            return "I can't verify that model right now because no configured provider catalog responded."
        result = f"I couldn't find {requested} in the model catalogs that responded."
        if unavailable:
            result += f" {unavailable} configured provider(s) could not be checked."
        return result

    if not reachable:
        return "I couldn't verify installed or loaded models because no configured provider catalog responded."
    names = list(dict.fromkeys(
        str(model.get("name")) for _label, model in all_models if model.get("name")
    ))[:12]
    loaded_names = list(dict.fromkeys(
        f"{model.get('name')} on {label}" for label, model in all_loaded if model.get("name")
    ))[:8]
    result = f"I checked {len(reachable)} configured model provider(s) just now."
    if names:
        result += " Installed: " + ", ".join(names) + "."
    else:
        result += " No installed models were reported."
    if loaded_names:
        result += " Loaded now: " + ", ".join(loaded_names) + "."
    elif all(endpoint.get("loaded_status") == "CURRENT" for endpoint in endpoints if isinstance(endpoint, dict)):
        result += " No models are currently reported as loaded."
    else:
        result += " Current loaded-model state is partly unavailable."
    if unavailable:
        result += f" I couldn't check {unavailable} other configured provider(s)."
    return result + " Catalog access does not prove a generation request works or establish free GPU capacity."


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
    elif name == "homelab_inference_inventory":
        result = homelab_inference_inventory()
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
