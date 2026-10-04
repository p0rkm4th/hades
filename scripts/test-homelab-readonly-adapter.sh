#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path("integrations/homelab-readonly")
spec = importlib.util.spec_from_file_location("homelab_reconcile", root / "reconcile.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
result = module.summarize(
    {"data": [{"type": "qemu", "name": "dinner-app", "node": "storage-alpha", "status": "running"}]},
    {"results": [{"name": "dinner-app", "planned_node": "Beta", "status": "active"}]},
    {"monitors": [{"name": "dinner-app", "status": "down", "last_updated": "2026-09-14T11:40:00+00:00"}]},
    now=now,
)
resource = result["resources"][0]
assert result["status"] == "OK"
assert result["online_names"] == ["dinner-app"]
assert result["source_counts"] == {
    "proxmox_runtime_rows": 1,
    "netbox_inventory_rows": 1,
    "kuma_monitor_rows": 1,
    "composed_resources": 1,
    "identity_unlinked_resources": 0,
}
assert result["availability_summary"] == [{"name": "dinner-app", "status": "down", "freshness": "STALE"}]
assert result["answer_contract"]["writes_performed"] is False
assert resource["runtime"]["node"] == "storage-alpha"
assert resource["runtime_status"] == "running"
assert resource["currently_online"] is True
assert resource["inventory"]["planned_node"] == "Beta"
assert resource["availability"]["status"] == "down"
assert resource["availability_freshness"] == "STALE"
assert resource["conflicts"]
assert resource["identity"]["canonical_id"] is None
assert resource["identity"]["link_status"] == "NAME_MATCH_ONLY"
assert result["source_counts"]["identity_unlinked_resources"] == 0
assert result["authority"]["runtime"] == "Proxmox"
vm_result = module.summarize(
    {"data": [{"type": "qemu", "vmid": 102, "name": "hades-core", "node": "hypervisor-alpha", "status": "running"}]},
    {"results": []},
    {"monitors": []},
)
vm_resource = vm_result["resources"][0]
assert vm_result["online_names"] == ["hades-core"]
assert vm_result["inventory_only_names"] == []
assert vm_resource["runtime"] == {
    "name": "hades-core", "node": "hypervisor-alpha", "type": "qemu", "vmid": 102, "status": "running"
}
assert vm_resource["inventory"] is None
assert vm_resource["currently_online"] is True
future = module.summarize(
    {"data": [{"type": "qemu", "name": "clock-skewed", "node": "storage-alpha", "status": "running"}]},
    {"results": []},
    {"monitors": [{"name": "clock-skewed", "status": "up", "last_updated": "2026-09-14T12:05:00+00:00"}]},
    now=now,
)
assert future["resources"][0]["availability_freshness"] == "UNKNOWN"
duplicate_guest_names = module.summarize(
    {"data": [
        {"type": "qemu", "vmid": 100, "name": "hades-core", "node": "hypervisor-alpha", "status": "stopped"},
        {"type": "qemu", "vmid": 102, "name": "hades-core", "node": "hypervisor-alpha", "status": "running"},
    ]},
    {"results": []},
    {"monitors": []},
)
assert duplicate_guest_names["source_counts"]["proxmox_runtime_rows"] == 2
assert duplicate_guest_names["source_counts"]["composed_resources"] == 2
assert {
    (row["runtime"]["vmid"], row["runtime_status"], bool(row["conflicts"]))
    for row in duplicate_guest_names["resources"]
} == {(100, "stopped", True), (102, "running", True)}
assert all(
    any("remain separate by stable source identity" in conflict for conflict in row["conflicts"])
    for row in duplicate_guest_names["resources"]
)
linked_identity = module.summarize(
    {"data": [{
        "id": "node/alpha", "type": "node", "node": "alpha", "name": "alpha",
        "status": "online", "source_identity": "proxmox:alpha:node:alpha",
    }]},
    {"results": [{"id": 41, "name": "inventory-alpha", "role": "compute"}]},
    {"monitors": [{
        "id": "9", "source_identity": "kuma:monitor:9", "name": "alpha-api",
        "status": "down", "last_updated": "2026-09-14T11:59:00+00:00",
        "monitor_type": "http",
    }]},
    now=now,
    identity_links={"proxmox:alpha:node:alpha": 41, "kuma:monitor:9": 41},
)
host = next(row for row in linked_identity["resources"] if row["inventory"])
monitor = next(row for row in linked_identity["resources"] if row["availability"])
assert host["runtime_status"] == "online" and host["inventory"]["id"] == 41
assert host["identity"] == {
    "canonical_id": "netbox:device:41",
    "source_identities": {
        "proxmox": ["proxmox:alpha:node:alpha"],
        "netbox": ["netbox:device:41"],
    },
    "link_status": "STABLE",
}, host
assert host["availability"] is None
assert monitor["runtime"] is None and monitor["availability"]["status"] == "down"
assert monitor["related_inventory_device_id"] == 41
assert monitor["identity"]["canonical_id"] is None
assert monitor["identity"]["source_identities"] == {"kuma": ["kuma:monitor:9"]}
assert monitor["identity"]["link_status"] == "RELATED_PARENT"
linked_same_label = module.summarize(
    {"data": [{
        "id": "node/alpha", "type": "node", "node": "alpha", "name": "alpha",
        "status": "online", "source_identity": "proxmox:alpha:node:alpha",
    }]},
    {"results": [{"id": 41, "name": "alpha"}]},
    None,
    identity_links={"proxmox:alpha:node:alpha": 41},
)
assert len(linked_same_label["resources"]) == 1, linked_same_label["resources"]
assert linked_same_label["resources"][0]["identity"]["canonical_id"] == "netbox:device:41"
assert linked_same_label["resources"][0]["conflicts"] == [], linked_same_label["resources"][0]
assert linked_same_label["conflicts"] == [], linked_same_label["conflicts"]
assert linked_same_label["source_counts"]["identity_unlinked_resources"] == 0
unlinked_same_label = module.summarize(
    {"data": [{"id": "qemu/900", "type": "qemu", "vmid": 900, "node": "alpha", "name": "same-label", "status": "running", "source_identity": "proxmox:alpha:qemu:900"}]},
    {"results": [{"id": 42, "name": "same-label"}]},
    None,
)
assert unlinked_same_label["source_counts"]["composed_resources"] == 2
assert all(any("no stable identity link" in conflict for conflict in row["conflicts"]) for row in unlinked_same_label["resources"])
assert unlinked_same_label["source_counts"]["identity_unlinked_resources"] == 1
assert any(row["identity"]["canonical_id"] is None for row in unlinked_same_label["resources"])
assert any(row["identity"]["canonical_id"] == "netbox:device:42" for row in unlinked_same_label["resources"])
assert any(row["identity"]["source_identities"].get("proxmox") == ["proxmox:alpha:qemu:900"] for row in unlinked_same_label["resources"])
linked_host_duplicate_inventory = module.summarize(
    {"data": [{
        "id": "node/alpha", "type": "node", "node": "alpha", "name": "alpha",
        "status": "online", "source_identity": "proxmox:alpha:node:alpha",
    }]},
    {"results": [{"id": 41, "name": "alpha"}, {"id": 42, "name": "alpha"}]},
    None,
    identity_links={"proxmox:alpha:node:alpha": 41},
)
linked_inventory_rows = {
    row["identity"]["source_identities"].get("netbox", [None])[0]: row
    for row in linked_host_duplicate_inventory["resources"]
    if row["identity"]["source_identities"].get("netbox")
}
assert linked_inventory_rows["netbox:device:41"]["identity"]["canonical_id"] == "netbox:device:41"
assert linked_inventory_rows["netbox:device:41"]["conflicts"] == []
assert any("no stable identity link" in item for item in linked_inventory_rows["netbox:device:42"]["conflicts"])
assert linked_host_duplicate_inventory["source_counts"]["identity_unlinked_resources"] == 0
kuma_parent_name_collision = module.summarize(
    None,
    {"results": [{"id": 43, "name": "shared-host-label"}]},
    {"monitors": [{
        "id": "77", "source_identity": "kuma:monitor:77", "name": "shared-host-label",
        "status": "up", "last_updated": "2026-09-14T11:59:00+00:00",
    }]},
    identity_links={"kuma:monitor:77": 43},
)
assert len(kuma_parent_name_collision["resources"]) == 2
assert all(any("no stable identity link" in item for item in row["conflicts"])
           for row in kuma_parent_name_collision["resources"])
kuma_collision_monitor = next(
    row for row in kuma_parent_name_collision["resources"] if row["availability"]
)
assert kuma_collision_monitor["identity"]["link_status"] == "RELATED_PARENT"
inventory_only = module.summarize(
    {"data": []},
    {"results": [{"name": "compute-alpha"}]},
    None,
)
assert inventory_only["online_names"] == []
assert inventory_only["inventory_only_names"] == ["compute-alpha"]
assert inventory_only["resources"][0]["runtime_status"] == "NOT_OBSERVED"
assert inventory_only["resources"][0]["currently_online"] is False
server_source = (Path(root) / "server.py").read_text()
assert "token_path.is_symlink()" in server_source
assert "MAX_TOKEN_BYTES" in server_source
assert "homelab_discovery_candidates" in server_source
assert "homelab_discovery_scan" in server_source
assert "homelab_compute_capabilities" in server_source
assert 'unknown tool: {name}' in server_source
assert "call_tool(params.name, params.arguments)" in server_source
assert 'errors.append(f"{label} source is not configured")' in server_source
assert "HADES_DISCOVERY_ALLOWED_NETWORKS" in server_source
assert "run_bounded_scan" in server_source
assert "propose_inventory_candidates" in server_source
assert "does not run Nmap" in server_source
sys.path.insert(0, str(root))
config_spec = importlib.util.spec_from_file_location("homelab_config", root / "config.py")
config = importlib.util.module_from_spec(config_spec)
config_spec.loader.exec_module(config)
import os
os.environ.update({
    "HADES_PROXMOX_URL": "https://pve.example.test:8006/api2/json",
    "HADES_NETBOX_URL": "https://netbox.example.test",
    "HADES_UPTIME_KUMA_URL": "https://status.example.test",
    "HADES_UPTIME_KUMA_STATUS_SLUG": "hades-status",
})
assert config.source_specs() == (
    ("https://pve.example.test:8006/api2/json/cluster/resources", ""),
    ("https://netbox.example.test/api/dcim/devices/", ""),
    ("https://status.example.test/api/status-page/heartbeat/hades-status", ""),
)
assert config.netbox_services_spec() == (
    "https://netbox.example.test/api/ipam/services/", "",
)
os.environ["HADES_PROXMOX_RESOURCES_URLS"] = "https://a.example.test/r,https://b.example.test/r"
os.environ["HADES_PROXMOX_TOKEN_FILES"] = "/run/a,/run/b"
os.environ["HADES_PROXMOX_TOKEN_IDS"] = "svc-hades-ro@pve!a,svc-hades-ro@pve!b"
assert config.proxmox_specs() == (
    ("https://a.example.test/r", "/run/a"),
    ("https://b.example.test/r", "/run/b"),
)
assert config.proxmox_token_ids() == (
    "svc-hades-ro@pve!a",
    "svc-hades-ro@pve!b",
)
os.environ["HADES_PROXMOX_SOURCE_IDS"] = "alpha,beta"
assert config.proxmox_source_ids() == ("alpha", "beta")
print("PASS homelab adapter preserves runtime/inventory/availability authority")
print("PASS homelab adapter discloses node conflict and stale Kuma observation")
print("PASS Proxmox runtime exposes configured guest without inventing a NetBox record")
print("PASS future monitoring observations fail closed as unknown")
print("PASS duplicate guest display names preserve each stable Proxmox identity")
print("PASS explicit Proxmox-to-NetBox identity links correlate hosts without collapsing service monitors")
print("PASS stable same-name records remain unlinked without an explicit crosswalk")
print("PASS homelab MCP exposes review-only discovery candidates")
print("PASS documented homelab bases resolve to bounded read endpoints")
PY

python3 - <<'PY'
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "homelab_services", Path("integrations/homelab-readonly/services.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.project_netbox_services(
    {"results": [{
        "name": "Minecraft Java",
        "device": {"id": 7, "name": "service-host-alpha"},
        "port_mappings": ["TCP/25565", "udp/25565", "tcp/99999", "tcp/any"],
        "ipaddresses": [],
        "untrusted_secret_like_field": "must-not-escape",
    }]},
    {"results": [{"id": 7, "name": "service-host-alpha", "primary_ip4": {"address": "192.0.2.75/24"}}]},
)
assert result["status"] == "OK" and result["writes_performed"] is False
assert result["inventory_is_not_liveness"] is True
assert result["services"] == [{
    "name": "Minecraft Java", "parent_type": "device", "parent_name": "service-host-alpha",
    "addresses": ["192.0.2.75"], "address_source": "NetBox parent primary IP",
    "port_mappings": ["tcp/25565", "udp/25565"], "runtime_status": "UNKNOWN",
}]
assert "untrusted_secret_like_field" not in str(result)
print("PASS NetBox service projection joins parent address, validates protocol/ports, and never claims liveness")
PY

python3 - <<'PY'
import atexit
import json
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path

# Keep this public acceptance test independent of Hermes, MCP, PyYAML, and the
# sibling private hades-infra checkout. Only the adapter behavior under test is
# real; its transport types and capability-matrix parser are lightweight test
# doubles, and the matrix fixture is synthetic JSON (valid YAML input shape).
anyio = types.ModuleType("anyio")
anyio.to_thread = types.SimpleNamespace(run_sync=lambda callback: callback())
anyio.run = lambda *_args, **_kwargs: None
yaml = types.ModuleType("yaml")
yaml.safe_load = json.loads
yaml.YAMLError = ValueError

class McpValue:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class McpServer:
    def __init__(self, *_args, **_kwargs):
        pass

mcp = types.ModuleType("mcp")
mcp_server = types.ModuleType("mcp.server")
mcp_lowlevel = types.ModuleType("mcp.server.lowlevel")
mcp_lowlevel.Server = McpServer
mcp_stdio = types.ModuleType("mcp.server.stdio")
mcp_stdio.stdio_server = lambda: None
mcp_types = types.ModuleType("mcp.types")
for class_name in ("CallToolResult", "ListToolsResult", "TextContent", "Tool"):
    setattr(mcp_types, class_name, type(class_name, (McpValue,), {}))
sys.modules.update({
    "anyio": anyio,
    "yaml": yaml,
    "mcp": mcp,
    "mcp.server": mcp_server,
    "mcp.server.lowlevel": mcp_lowlevel,
    "mcp.server.stdio": mcp_stdio,
    "mcp.types": mcp_types,
})

matrix_dir = Path(tempfile.mkdtemp(prefix="hades-homelab-matrix-"))
atexit.register(shutil.rmtree, matrix_dir, ignore_errors=True)
matrix_path = matrix_dir / "capability-matrix.json"
matrix_path.write_text(json.dumps({"machines": [
    {"name": "compute-alpha", "address": "192.0.2.69", "os": "Fedora",
     "cpu": "synthetic", "ram_gib": 64, "gpus": ["GPU Model A"],
     "nvidia_driver": "synthetic", "cuda_container_capability": "unknown",
     "runtime_status": "observed-only", "ssh": "synthetic", "role": "inference"},
    {"name": "compute-beta", "address": "192.0.2.73", "os": "Fedora",
     "cpu": "synthetic", "ram_gib": 64, "gpus": ["GPU Model B"],
     "nvidia_driver": "synthetic", "cuda_container_capability": "unknown",
     "runtime_status": "observed-only", "ssh": "synthetic", "role": "inference"},
    {"name": "compute-gamma", "address": "192.0.2.152", "os": "Linux",
     "cpu": "synthetic", "ram_gib": 64, "gpus": ["GPU Model C"],
     "nvidia_driver": "synthetic", "cuda_container_capability": "unknown",
     "runtime_status": "observed-only", "ssh": "synthetic", "role": "inference"},
]}), encoding="utf-8")
os.environ["HADES_CAPABILITY_MATRIX_FILE"] = str(matrix_path)

root = Path("integrations/homelab-readonly").resolve()
sys.path.insert(0, str(root))
import server

assert server._proxmox_permissions_url(
    "https://pve.example.test:8006/api2/json/cluster/resources"
) == "https://pve.example.test:8006/api2/json/access/permissions"
assert server._proxmox_guest_visibility({"data": {
    "/vms": {"VM.Audit": 1},
}}) == {"status": "COMPLETE", "scope": "ALL_GUESTS", "scoped_guest_count": None}
assert server._proxmox_guest_visibility({"data": {
    "/": {"VM.Audit": 1}, "/vms/102": {"VM.Audit": 1, "NoAccess": 1},
}}) == {"status": "PARTIAL", "scope": "ALL_GUESTS_WITH_EXCLUSIONS", "scoped_guest_count": None}
assert server._proxmox_guest_visibility({"data": {
    "/vms/101": {"VM.Audit": 1}, "/vms/102": {"VM.Audit": 1},
}}) == {"status": "PARTIAL", "scope": "SELECTED_GUESTS", "scoped_guest_count": 2}
assert server._proxmox_guest_visibility({"data": {
    "/pool/inference": {"VM.Audit": 1},
}}) == {"status": "PARTIAL", "scope": "SELECTED_GUESTS", "scoped_guest_count": None}
assert server._proxmox_guest_visibility({"data": {}}) == {
    "status": "PARTIAL", "scope": "NO_GUEST_AUDIT", "scoped_guest_count": 0,
}
assert server._aggregate_proxmox_guest_visibility([
    {"status": "COMPLETE", "scope": "ALL_GUESTS"},
    {"status": "UNKNOWN", "scope": "UNKNOWN"},
]) == {"status": "UNKNOWN", "scope": "MIXED"}
print("PASS effective Proxmox guest visibility distinguishes cluster-wide, selected, and unknown scope")

os.environ.update({
    "HADES_UPTIME_KUMA_URL": "https://status.example.test",
    "HADES_UPTIME_KUMA_STATUS_SLUG": "hades-status",
})
kuma = server._normalize_kuma_status({
    "publicGroupList": [{"monitorList": [
        {"id": 7, "name": "host-alpha", "type": "ping"},
        {"id": 8, "name": "host-beta", "type": "ping"},
    ]}],
    "heartbeatList": {
        "7": [{"status": 1, "time": "2026-09-16 09:00:00.000", "ping": 84}],
        "8": [{"status": 0, "time": "2026-09-16 09:00:01.000", "ping": 70001}],
    },
})
assert kuma["monitors"] == [
    {"name": "host-alpha", "status": "up", "last_updated": "2026-09-16 09:00:00.000", "monitor_type": "ping", "id": "7", "source_identity": "kuma:monitor:7", "ping_ms": 84},
    {"name": "host-beta", "status": "down", "last_updated": "2026-09-16 09:00:01.000", "monitor_type": "ping", "id": "8", "source_identity": "kuma:monitor:8"},
]
assert server._kuma_config_url() == "https://status.example.test/api/status-page/hades-status"
assert server._proxmox_source_identity("alpha", {"type": "node", "id": "node/alpha"}) == "proxmox:alpha:node:alpha"
assert server._proxmox_source_identity("alpha", {"type": "qemu", "id": "qemu/102"}) == "proxmox:alpha:qemu:102"
assert server._proxmox_source_identity("", {"type": "node", "node": "alpha"}) is None
identity_path = matrix_dir / "identity-links.json"
identity_path.write_text(json.dumps({"links": [
    {"source_identity": "proxmox:synthetic:node:alpha", "netbox_device_id": 75},
]}), encoding="utf-8")
identity_path.chmod(0o600)
os.environ["HADES_HOMELAB_IDENTITY_LINKS_FILE"] = str(identity_path)
assert server._read_identity_links() == {"proxmox:synthetic:node:alpha": 75}
identity_path.chmod(0o644)
try:
    server._read_identity_links()
except ValueError as exc:
    assert "mode 0600 or 0640" in str(exc)
else:
    raise AssertionError("identity-link file with unsafe permissions must be rejected")
identity_path.chmod(0o600)
print("PASS identity crosswalk is bounded, schema-checked, and rejects unsafe permissions")

from datetime import datetime, timezone
now = datetime.now(timezone.utc)
fresh_time = now.isoformat()
latency_result = server.summarize(
    {"data": []}, {"results": []},
    {"monitors": [{"name": "Router ping", "status": "up", "last_updated": fresh_time, "ping_ms": 84}]},
    now=now,
)
assert latency_result["availability_summary"] == [
    {"name": "Router ping", "status": "up", "freshness": "FRESH", "ping_ms": 84}
]
for unsafe_ping in (-1, 60001, True, float("nan"), float("inf"), "84"):
    normalized = server.summarize(
        {"data": []}, {"results": []},
        {"monitors": [{"name": "bad ping", "status": "up", "last_updated": fresh_time, "ping_ms": unsafe_ping}]},
        now=now,
    )
    assert "ping_ms" not in normalized["availability_summary"][0], normalized

# Exercise the complete bounded MCP summary path, not only the lower-level
# reconciliation helper. Runtime telemetry is useful for owner status answers,
# but raw/unrecognized upstream fields must remain excluded.
os.environ.update({
    "HADES_PROXMOX_RESOURCES_URLS": "https://pve.example.test/cluster/resources",
    "HADES_PROXMOX_TOKEN_FILES": "/run/synthetic-proxmox-token",
    "HADES_PROXMOX_TOKEN_IDS": "svc-hades-ro@pve!synthetic",
    "HADES_PROXMOX_SOURCE_IDS": "synthetic",
    "HADES_NETBOX_DEVICES_URL": "https://netbox.example.test/api/dcim/devices/",
    "HADES_NETBOX_SERVICES_URL": "https://netbox.example.test/api/ipam/services/",
    "HADES_KUMA_STATUS_URL": "https://status.example.test/api/status-page/heartbeat/hades-status",
})
original_fetch = server._fetch
runtime_fixture = {
    "type": "qemu", "vmid": 102, "name": "hades-core", "node": "hypervisor-alpha",
    "status": "running", "cpu": 0.25, "maxcpu": 16, "mem": 1073741824,
    "maxmem": 8589934592, "disk": 10737418240, "maxdisk": 53687091200,
    "uptime": 3600, "unrelated_secret_like_field": "must-not-escape",
}
node_fixture = {
    "id": "node/hypervisor-alpha", "type": "node", "node": "hypervisor-alpha",
    "name": "hypervisor-alpha", "status": "online", "cpu": 0.375,
    "mem": 4 * 1024**3, "maxmem": 16 * 1024**3,
}
device_fixture = {
    "id": 75, "name": "service-host-alpha", "primary_ip4": {"address": "192.0.2.75/24"},
}
service_fixture = {
    "name": "Minecraft Java", "device": {"id": 75, "name": "service-host-alpha"},
    "port_mappings": ["tcp/25565"], "ipaddresses": [],
    "secret_like_field": "must-not-escape",
}
def fixture_fetch(url, *_args, **_kwargs):
    if url == "https://pve.example.test/cluster/resources":
        return {"data": [node_fixture, runtime_fixture]}
    if url == "https://pve.example.test/access/permissions":
        return {"data": {"/vms": {"VM.Audit": 1}}}
    if url == "https://netbox.example.test/api/dcim/devices/":
        return {"results": [device_fixture]}
    if url == "https://netbox.example.test/api/ipam/services/":
        return {"results": [service_fixture]}
    if url == "https://status.example.test/api/status-page/heartbeat/hades-status":
        return {"heartbeatList": {"5": [{"status": 1, "time": "2026-09-14 12:00:00.000"}]}}
    if url == "https://status.example.test/api/status-page/hades-status":
        return {"publicGroupList": [{"monitorList": [{"id": 5, "name": "monitor-alpha", "type": "ping"}]}]}
    raise AssertionError(f"unexpected synthetic adapter URL: {url}")
server._fetch = fixture_fetch
summary = server.homelab_summary()
assert summary["status"] == "OK", summary
assert summary["source_counts"]["proxmox_runtime_rows"] == 2, summary
runtime_row = next(row for row in summary["resources"] if row["name"] == "hades-core")
assert runtime_row["runtime"] == {
    "name": "hades-core", "node": "hypervisor-alpha", "type": "qemu", "vmid": 102,
    "status": "running", "cpu": 0.25, "maxcpu": 16,
    "mem": 1073741824, "maxmem": 8589934592,
    "disk": 10737418240, "maxdisk": 53687091200, "uptime": 3600,
}, runtime_row
assert runtime_row["currently_online"] is True
assert isinstance(runtime_row["identity"], dict)
assert "link_status" in runtime_row["identity"]
assert summary["source_counts"]["netbox_service_rows"] == 1
assert summary["service_catalog"]["retrieved_at"]
assert {row["source"] for row in summary["source_observations"]} == {
    "Proxmox:synthetic", "Proxmox guest visibility (synthetic)", "NetBox", "Uptime Kuma",
}
assert summary["proxmox_guest_visibility"] == {
    "status": "COMPLETE", "scope": "ALL_GUESTS",
    "endpoints": [{"status": "COMPLETE", "scope": "ALL_GUESTS", "scoped_guest_count": None}],
    "read_only": True,
}
assert summary["sources"] == summary["source_observations"]
assert isinstance(summary["source_counts"]["identity_unlinked_resources"], int)
guest_index = summary["proxmox_guest_inventory"]
assert guest_index["status"] == "COMPLETE", guest_index
assert guest_index["endpoints"][0]["source_id"] == "synthetic"
assert guest_index["endpoints"][0]["status"] == "COMPLETE"
assert guest_index["endpoints"][0]["node_inventory_status"] == "OBSERVED"
assert guest_index["endpoints"][0]["nodes"] == [{
    "source_identity": "proxmox:synthetic:node:hypervisor-alpha",
    "node": "hypervisor-alpha", "name": "hypervisor-alpha", "status": "ONLINE",
}], guest_index
assert guest_index["endpoints"][0]["guests"] == [{
    "source_identity": "proxmox:synthetic:qemu:102",
    "node_identity": "proxmox:synthetic:node:hypervisor-alpha", "guest_type": "qemu",
    "guest_id": "102", "name": "hades-core", "node": "hypervisor-alpha",
    "status": "RUNNING",
}], guest_index
assert "192.0.2" not in str(guest_index)
node_metrics = summary["proxmox_node_metrics"]
assert node_metrics["status"] == "READABLE", node_metrics
assert node_metrics["writes_performed"] is False
node_sample = node_metrics["endpoints"][0]["nodes"][0]
assert node_sample == {
    "source_identity": "proxmox:synthetic:node:hypervisor-alpha",
    "node": "hypervisor-alpha",
    "name": "hypervisor-alpha", "status": "ONLINE",
    "observed_at": next(row["retrieved_at"] for row in summary["source_observations"]
                         if row["source"] == "Proxmox:synthetic"),
    "canonical_id": None,
    "identity_status": "UNLINKED",
    "cpu_fraction": 0.375,
    "memory_used_bytes": 4 * 1024**3,
    "memory_total_bytes": 16 * 1024**3,
}, node_sample
linked_node_metrics = server._project_proxmox_node_metrics(
    ("synthetic",), {"synthetic": [node_fixture]},
    [{"source": "Proxmox:synthetic", "status": "AVAILABLE", "retrieved_at": "synthetic-time"}],
    [], {"proxmox:synthetic:node:hypervisor-alpha": 75},
)
linked_node = linked_node_metrics["endpoints"][0]["nodes"][0]
assert linked_node["canonical_id"] == "netbox:device:75", linked_node
assert linked_node["identity_status"] == "LINKED", linked_node
missing_node_timestamp = server._project_proxmox_node_metrics(
    ("synthetic",), {"synthetic": [node_fixture]},
    [{"source": "Proxmox:synthetic", "status": "AVAILABLE"}], [],
)
assert missing_node_timestamp["status"] == "UNKNOWN", missing_node_timestamp
assert missing_node_timestamp["endpoints"][0]["error_code"] == "MISSING_SOURCE_TIMESTAMP"
assert missing_node_timestamp["endpoints"][0]["nodes"] == []
unstable_node_source = server._project_proxmox_node_metrics(
    ("",), {"endpoint-1": [node_fixture]},
    [{"source": "Proxmox:endpoint-1", "status": "AVAILABLE", "retrieved_at": "synthetic-time"}], [],
)
assert unstable_node_source["status"] == "UNKNOWN", unstable_node_source
assert unstable_node_source["endpoints"][0]["source_id"] is None
assert unstable_node_source["endpoints"][0]["error_code"] == "UNSTABLE_SOURCE_IDENTITY"
assert unstable_node_source["endpoints"][0]["nodes"] == []
large_guest_index = server._project_proxmox_guest_index(
    ("synthetic",),
    {"synthetic": [{
        "source_identity": f"proxmox:synthetic:qemu:{guest_id}",
        "type": "qemu", "vmid": guest_id, "status": "stopped",
    } for guest_id in range(1, 514)]},
    [{"source": "Proxmox:synthetic", "status": "AVAILABLE", "retrieved_at": "synthetic-time"}],
    [{"coverage": {"status": "COMPLETE", "scope": "ALL_GUESTS"}}],
)
assert large_guest_index["status"] == "PARTIAL"
assert large_guest_index["endpoints"][0]["truncated"] is True
assert len(large_guest_index["endpoints"][0]["guests"]) == 512
assert large_guest_index["endpoints"][0]["node_inventory_status"] == "UNKNOWN"
unstable_guest_index = server._project_proxmox_guest_index(
    ("",), {"endpoint-1": []},
    [{"source": "Proxmox:endpoint-1", "status": "AVAILABLE", "retrieved_at": "synthetic-time"}],
    [{"coverage": {"status": "COMPLETE", "scope": "ALL_GUESTS"}}],
)
assert unstable_guest_index["status"] == "PARTIAL", unstable_guest_index
assert unstable_guest_index["endpoints"][0]["status"] == "PARTIAL"
assert summary["service_catalog"]["services"] == [{
    "name": "Minecraft Java", "parent_type": "device", "parent_name": "service-host-alpha",
    "addresses": ["192.0.2.75"], "address_source": "NetBox parent primary IP",
    "port_mappings": ["tcp/25565"], "runtime_status": "UNKNOWN",
}]
assert "secret_like_field" not in str(summary)
assert "unrelated_secret_like_field" not in str(summary)
server._fetch = original_fetch
print("PASS homelab MCP summary retains bounded runtime telemetry without unrelated upstream fields")

# Proxmox backup evidence is read-only, scope-filtered, bounded, and distinct
# from proof of artifact contents or restoreability.
assert "homelab_backup_status" in {tool.name for tool in server.TOOLS}
def backup_fetch(url, *_args, **_kwargs):
    if url.endswith("/access/permissions"):
        return {"data": {"/vms": {"VM.Audit": 1}}}
    if url.endswith("/cluster/backup"):
        return {"data": [{"id": "nightly", "schedule": "02:00", "storage": "backup-store", "enabled": 1}]}
    if url.endswith("/cluster/resources"):
        return {"data": [{"type": "node", "node": "hypervisor-alpha"}]}
    if "/nodes/hypervisor-alpha/tasks?" in url:
        return {"data": [
            {"id": "102", "status": "OK", "starttime": 1700000000, "endtime": 1700000300, "upid": "UPID:must-not-escape"},
            {"id": "103", "status": "ERROR: private failure detail", "endtime": 1700000200},
            {"status": "OK", "endtime": 1700000100},
        ]}
    raise AssertionError(f"unexpected synthetic backup URL: {url}")

server._fetch = backup_fetch
backup_report = server.homelab_backup_status()
assert backup_report["status"] == "READABLE", backup_report
backup_endpoint = backup_report["endpoints"][0]
assert backup_endpoint["jobs_status"] == "HEALTHY"
assert backup_endpoint["tasks_status"] == "HEALTHY"
assert backup_endpoint["task_scope"] == "ALL_GUESTS"
assert {task["status"] for task in backup_endpoint["tasks"]} == {"OK", "ERROR"}
assert len(backup_endpoint["unattributed_tasks"]) == 1
assert "UPID:" not in json.dumps(backup_report)
assert "private-user" not in json.dumps(backup_report)
assert "private failure detail" not in json.dumps(backup_report)
backup_text = server.format_homelab_backup_status(backup_report)
assert "doesn't verify backup contents" in backup_text
assert backup_report["retrieved_at"] in backup_text
assert backup_report["formatted_summary"] == backup_text
print("PASS Proxmox backup reads disclose scope/freshness and avoid artifact/restore claims")

def selected_backup_fetch(url, *_args, **_kwargs):
    if url.endswith("/access/permissions"):
        return {"data": {"/vms/102": {"VM.Audit": 1}}}
    if url.endswith("/cluster/backup"):
        return {"data": []}
    if url.endswith("/cluster/resources"):
        return {"data": [{"type": "node", "node": "hypervisor-alpha"}]}
    if "/nodes/hypervisor-alpha/tasks?" in url:
        return {"data": [
            {"id": "102", "status": "OK", "endtime": 1700000300},
            {"id": "103", "status": "OK", "endtime": 1700000200},
        ]}
    raise AssertionError(f"unexpected selected-scope backup URL: {url}")

server._fetch = selected_backup_fetch
selected_backup = server.homelab_backup_status()["endpoints"][0]
assert selected_backup["task_scope"] == "SELECTED_GUESTS"
assert [task["guest_id"] for task in selected_backup["tasks"]] == ["102"]
assert selected_backup["tasks_status"] == "PARTIAL"
server._fetch = original_fetch
print("PASS Proxmox backup task history is filtered to effective VM.Audit scope")

# Recent activity composes bounded Proxmox task history with NetBox record
# timestamps, preserves partial scope, and avoids claiming a complete log.
from datetime import datetime, timezone
activity_now = datetime.now(timezone.utc).isoformat()
def activity_fetch(url, *_args, **_kwargs):
    if url.endswith("/access/permissions"):
        return {"data": {"/vms": {"VM.Audit": 1}}}
    if url.endswith("/cluster/resources"):
        return {"data": [
            {"type": "node", "node": "hypervisor-alpha"},
            {"type": "qemu", "vmid": 102, "name": "hades-core"},
        ]}
    if "/nodes/hypervisor-alpha/tasks?" in url:
        return {"data": [
            {"id": "102", "type": "qmstart", "status": "OK", "starttime": int(datetime.now().timestamp())},
            {"id": "999", "type": "qmstop", "status": "OK", "starttime": int(datetime.now().timestamp())},
            {"id": "102", "type": "qmstart", "status": "OK", "starttime": 1},
        ]}
    if url.startswith("https://netbox.example.test/api/dcim/devices/?"):
        return {"count": 1, "results": [{"id": 75, "name": "service-host-alpha", "last_updated": activity_now}]}
    if url.startswith("https://netbox.example.test/api/ipam/services/?"):
        return {"count": 1, "results": [{"id": 21, "name": "Minecraft Java", "last_updated": activity_now}]}
    raise AssertionError(f"unexpected synthetic activity URL: {url}")

server._fetch = activity_fetch
activity = server.homelab_recent_activity(24)
assert activity["status"] == "READABLE", activity
activity_endpoint = activity["endpoints"][0]
assert activity_endpoint["scope"] == "ALL_GUESTS", activity_endpoint
assert {(row["guest_id"], row["task_type"]) for row in activity_endpoint["events"]} == {
    ("102", "qmstart"), ("999", "qmstop"),
}, activity_endpoint
assert {row["object_type"] for row in activity["netbox"]["objects"]} == {"device", "service"}
activity_text = server.format_homelab_recent_activity(activity)
assert "Recent recorded activity" in activity_text and "complete homelab change log" in activity_text
assert "private" not in activity_text.casefold()
server._fetch = original_fetch
print("PASS recent activity composes scoped Proxmox tasks and NetBox timestamps without claiming a complete change log")

# A failed independent Proxmox endpoint must not discard rows retrieved from
# another endpoint, and the summary must preserve per-source retrieval status.
os.environ.update({
    "HADES_PROXMOX_RESOURCES_URLS": "https://pve-a.example.test/cluster/resources,https://pve-b.example.test/cluster/resources",
    "HADES_PROXMOX_SOURCE_IDS": "alpha,beta",
})
alpha_resource_reads = 0
def partial_fetch(url, *_args, **_kwargs):
    global alpha_resource_reads
    if url == "https://pve-a.example.test/cluster/resources":
        alpha_resource_reads += 1
        if alpha_resource_reads > 1:
            raise OSError("synthetic endpoint unavailable on the repeated read")
        return {"data": [{
            "id": "qemu/102", "type": "qemu", "vmid": 102,
            "name": "hades-core", "node": "alpha", "status": "running",
        }]}
    if url == "https://pve-b.example.test/cluster/resources":
        raise OSError("synthetic endpoint timeout")
    if url == "https://pve-a.example.test/access/permissions":
        return {"data": {"/vms/102": {"VM.Audit": 1}}}
    if url == "https://pve-b.example.test/access/permissions":
        raise OSError("synthetic permission read timeout")
    if url == "https://netbox.example.test/api/dcim/devices/":
        return {"results": [device_fixture]}
    if url == "https://netbox.example.test/api/ipam/services/":
        return {"results": [service_fixture]}
    if url == "https://status.example.test/api/status-page/heartbeat/hades-status":
        return {"heartbeatList": {"5": [{"status": 1, "time": "2026-09-14 12:00:00.000"}]}}
    if url == "https://status.example.test/api/status-page/hades-status":
        return {"publicGroupList": [{"monitorList": [{"id": 5, "name": "monitor-alpha", "type": "ping"}]}]}
    raise AssertionError(f"unexpected synthetic adapter URL: {url}")
server._fetch = partial_fetch
partial = server.homelab_summary()
assert partial["status"] == "PARTIAL", partial
assert any((row["runtime"] or {}).get("vmid") == 102 for row in partial["resources"])
pve_sources = [row for row in partial["source_observations"]
               if row["source"].startswith("Proxmox:") and "guest visibility" not in row["source"]]
assert [(row["source"], row["status"]) for row in pve_sources] == [
    ("Proxmox:alpha", "AVAILABLE"), ("Proxmox:beta", "UNAVAILABLE"),
]
assert pve_sources[0]["retrieved_at"] and pve_sources[0]["rows"] == 1
assert pve_sources[1]["retrieved_at"] is None
assert partial["proxmox_guest_visibility"]["status"] == "PARTIAL"
assert partial["proxmox_guest_visibility"]["scope"] == "MIXED"
partial_node_metrics = partial["proxmox_node_metrics"]
assert partial_node_metrics["status"] == "PARTIAL", partial_node_metrics
assert [row["status"] for row in partial_node_metrics["endpoints"]] == ["AVAILABLE", "UNAVAILABLE"]
assert partial_node_metrics["endpoints"][0]["node_inventory_status"] == "UNKNOWN"
partial_guest_sources = {
    row["source_id"]: row for row in partial["proxmox_guest_inventory"]["endpoints"]
}
assert partial_guest_sources["alpha"]["status"] == "PARTIAL", partial_guest_sources
assert partial_guest_sources["beta"]["status"] == "UNAVAILABLE", partial_guest_sources
assert partial_guest_sources["alpha"]["guests"][0]["source_identity"] == "proxmox:alpha:qemu:102"
assert next(row for row in partial["source_observations"] if row["source"] == "Uptime Kuma")["rows"] == 1
current_after_outage = server.homelab_summary()
assert current_after_outage["status"] == "PARTIAL", current_after_outage
assert current_after_outage["source_counts"]["proxmox_runtime_rows"] == 0
assert current_after_outage["online_names"] == []
assert not any(
    (row.get("runtime") or {}).get("vmid") == 102
    for row in current_after_outage["resources"]
)
latest_pve_sources = [row for row in current_after_outage["source_observations"]
                      if row["source"].startswith("Proxmox:") and "guest visibility" not in row["source"]]
assert [row["status"] for row in latest_pve_sources] == ["UNAVAILABLE", "UNAVAILABLE"]
assert all(row["retrieved_at"] is None for row in latest_pve_sources)
assert any(row["source"] == "Uptime Kuma" and row["status"] == "AVAILABLE"
           for row in current_after_outage["source_observations"])
server._fetch = original_fetch
print("PASS partial Proxmox outage preserves successful rows and does not promote a prior read")

def netbox_outage_fetch(url, *_args, **_kwargs):
    if url == "https://pve-a.example.test/cluster/resources":
        return {"data": [{
            "id": "qemu/102", "type": "qemu", "vmid": 102,
            "name": "hades-core", "node": "alpha", "status": "running",
        }]}
    if url == "https://pve-a.example.test/access/permissions":
        return {"data": {"/vms/102": {"VM.Audit": 1}}}
    if url in {
        "https://pve-b.example.test/cluster/resources",
        "https://pve-b.example.test/access/permissions",
        "https://netbox.example.test/api/dcim/devices/",
        "https://netbox.example.test/api/ipam/services/",
    }:
        raise OSError("synthetic canonical source unavailable")
    if url == "https://status.example.test/api/status-page/heartbeat/hades-status":
        return {"heartbeatList": {"5": [{"status": 1, "time": "2026-09-14 12:00:00.000"}]}}
    if url == "https://status.example.test/api/status-page/hades-status":
        return {"publicGroupList": [{"monitorList": [{"id": 5, "name": "monitor-alpha", "type": "ping"}]}]}
    raise AssertionError(f"unexpected synthetic outage URL: {url}")

# Seed a matching NetBox inventory row through its explicit stable identity
# link, then fail NetBox while Proxmox remains current. This proves a prior
# inventory join is not retained across summary calls after source failure.
original_identity_links = identity_path.read_text(encoding="utf-8")
identity_path.write_text(json.dumps({"links": [
    {"source_identity": "proxmox:alpha:qemu:102", "netbox_device_id": 102},
]}), encoding="utf-8")
identity_path.chmod(0o600)
seed_device = {"id": 102, "name": "hades-core", "role": "application"}
def netbox_seed_fetch(url, *_args, **_kwargs):
    if url == "https://pve-a.example.test/cluster/resources":
        return {"data": [{
            "id": "qemu/102", "type": "qemu", "vmid": 102,
            "name": "hades-core", "node": "alpha", "status": "running",
        }]}
    if url == "https://pve-b.example.test/cluster/resources":
        return {"data": []}
    if url in {
        "https://pve-a.example.test/access/permissions",
        "https://pve-b.example.test/access/permissions",
    }:
        return {"data": {"/vms": {"VM.Audit": 1}}}
    if url == "https://netbox.example.test/api/dcim/devices/":
        return {"results": [seed_device]}
    if url == "https://netbox.example.test/api/ipam/services/":
        return {"results": []}
    if url == "https://status.example.test/api/status-page/heartbeat/hades-status":
        return {"heartbeatList": {"5": [{"status": 1, "time": "2026-09-14 12:00:00.000"}]}}
    if url == "https://status.example.test/api/status-page/hades-status":
        return {"publicGroupList": [{"monitorList": [{"id": 5, "name": "monitor-alpha", "type": "ping"}]}]}
    raise AssertionError(f"unexpected synthetic NetBox seed URL: {url}")

server._fetch = netbox_seed_fetch
netbox_seed = server.homelab_summary()
seed_resource = next(
    row for row in netbox_seed["resources"]
    if (row.get("runtime") or {}).get("vmid") == 102
)
assert seed_resource["identity"]["canonical_id"] == "netbox:device:102", seed_resource
assert seed_resource["inventory_device_id"] == 102, seed_resource

# NetBox is now unavailable; the Proxmox guest stays live and Kuma keeps its
# old heartbeat. No inventory from the successful prior call may survive.
server._fetch = netbox_outage_fetch
netbox_outage = server.homelab_summary()
assert netbox_outage["status"] == "PARTIAL", netbox_outage
assert netbox_outage["source_counts"]["netbox_inventory_rows"] == 0
assert netbox_outage["source_counts"]["proxmox_runtime_rows"] == 1
assert "hades-core" in netbox_outage["online_names"]
outage_resource = next(
    row for row in netbox_outage["resources"]
    if (row.get("runtime") or {}).get("vmid") == 102
)
assert outage_resource["runtime"]["status"] == "running", outage_resource
assert outage_resource["inventory_device_id"] is None, outage_resource
assert outage_resource["identity"]["canonical_id"] is None, outage_resource
assert outage_resource["identity"]["link_status"] == "LINK_TARGET_MISSING", outage_resource
assert any("not returned by the current inventory read" in item for item in outage_resource["conflicts"]), outage_resource
netbox_observation = next(row for row in netbox_outage["source_observations"] if row["source"] == "NetBox")
assert netbox_observation["status"] == "UNAVAILABLE" and netbox_observation["retrieved_at"] is None
assert netbox_outage["service_catalog"]["status"] == "UNAVAILABLE"
assert netbox_outage["availability_summary"][0]["freshness"] == "STALE"
assert next(row for row in netbox_outage["source_observations"] if row["source"] == "Uptime Kuma")["status"] == "AVAILABLE"
identity_path.write_text(original_identity_links, encoding="utf-8")
identity_path.chmod(0o600)
server._fetch = original_fetch
print("PASS NetBox failure drops prior linked inventory while preserving live runtime and stale Kuma state")

result = server.homelab_compute_capabilities()
assert result["status"] == "OK"
assert result["read_only"] is True
assert result["authority"]["runtime"] == "Proxmox"
assert result["availability_not_provided"] is True
assert "Never label a machine online" in result["liveness_rule"]
assert all("runtime_status" not in row for row in result["machines"])
rows = {row["name"]: row for row in result["machines"]}
assert rows["compute-alpha"]["gpus"] == ["GPU Model A"]
assert rows["compute-beta"]["gpus"] == ["GPU Model B"]
assert rows["compute-gamma"]["gpus"] == ["GPU Model C"]
assert "does not imply current availability" in result["placement_rule"]
os.environ.pop("HADES_CAPABILITY_MATRIX_FILE", None)
assert server.homelab_compute_capabilities()["status"] == "UNAVAILABLE"

# Failure composition: a source outage must remain visible while preserving
# the authorities that did return data. Hardware metadata must not mask the
# partial live-source result.
original_summary = server.homelab_summary
original_compute = server.homelab_compute_capabilities
server.homelab_summary = lambda: {
    "status": "PARTIAL",
    "online_names": ["storage-alpha"],
    "errors": ["Uptime Kuma source unavailable"],
    "answer_contract": {"currently_online_source": "Proxmox runtime only"},
}
server.homelab_compute_capabilities = lambda: {
    "status": "OK",
    "machines": [{"name": "compute-alpha", "gpus": ["GPU Model A"]}],
    "availability_not_provided": True,
}
partial = server.homelab_owner_snapshot()
assert partial["status"] == "PARTIAL"
assert partial["summary"]["online_names"] == ["storage-alpha"]
assert partial["summary"]["errors"] == ["Uptime Kuma source unavailable"]
assert partial["compute"]["machines"][0]["name"] == "compute-alpha"
assert partial["answer_contract"]["inventory_is_not_liveness"] is True
assert partial["read_only"] is True
server.homelab_summary = original_summary
server.homelab_compute_capabilities = original_compute
print("PASS observed compute capability read is bounded, explicit, and read-only")
print("PASS owner snapshot preserves partial-source errors and authority boundaries")
PY

python -m py_compile integrations/homelab-readonly/reconcile.py integrations/homelab-readonly/server.py
echo 'PASS homelab MCP adapter is syntax-valid and read-only by construction'
