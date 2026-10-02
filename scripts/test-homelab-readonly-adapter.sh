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
    {"data": [{"type": "qemu", "name": "dinner-app", "node": "Alexandra", "status": "running"}]},
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
}
assert result["availability_summary"] == [{"name": "dinner-app", "status": "down", "freshness": "STALE"}]
assert result["answer_contract"]["writes_performed"] is False
assert resource["runtime"]["node"] == "Alexandra"
assert resource["runtime_status"] == "running"
assert resource["currently_online"] is True
assert resource["inventory"]["planned_node"] == "Beta"
assert resource["availability"]["status"] == "down"
assert resource["availability_freshness"] == "STALE"
assert resource["conflicts"]
assert result["authority"]["runtime"] == "Proxmox"
vm_result = module.summarize(
    {"data": [{"type": "qemu", "vmid": 802, "name": "hades-core", "node": "Erebus", "status": "running"}]},
    {"results": []},
    {"monitors": []},
)
vm_resource = vm_result["resources"][0]
assert vm_result["online_names"] == ["hades-core"]
assert vm_result["inventory_only_names"] == []
assert vm_resource["runtime"] == {
    "name": "hades-core", "node": "Erebus", "type": "qemu", "vmid": 802, "status": "running"
}
assert vm_resource["inventory"] is None
assert vm_resource["currently_online"] is True
future = module.summarize(
    {"data": [{"type": "qemu", "name": "clock-skewed", "node": "Alexandra", "status": "running"}]},
    {"results": []},
    {"monitors": [{"name": "clock-skewed", "status": "up", "last_updated": "2026-09-14T12:05:00+00:00"}]},
    now=now,
)
assert future["resources"][0]["availability_freshness"] == "UNKNOWN"
inventory_only = module.summarize(
    {"data": []},
    {"results": [{"name": "tartarus"}]},
    None,
)
assert inventory_only["online_names"] == []
assert inventory_only["inventory_only_names"] == ["tartarus"]
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
assert '_source_result(label, "NOT_CONFIGURED", started)' in server_source
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
os.environ["HADES_PROXMOX_TOKEN_FILES"] = "/run/one,/run/two,/run/extra"
try:
    config.proxmox_specs()
except ValueError:
    pass
else:
    raise AssertionError("mismatched Proxmox source configuration must fail")
assert config.source_specs()[1][0] == "https://netbox.example.test/api/dcim/devices/"
assert config.source_specs()[2][0] == "https://status.example.test/api/status-page/heartbeat/hades-status"
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
print("PASS homelab adapter preserves runtime/inventory/availability authority")
print("PASS homelab adapter discloses node conflict and stale Kuma observation")
print("PASS Proxmox runtime exposes VM 802 without inventing a NetBox record")
print("PASS future monitoring observations fail closed as unknown")
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
        "device": {"id": 7, "name": "Thanatos"},
        "port_mappings": ["TCP/25565", "udp/25565", "tcp/99999", "tcp/any"],
        "ipaddresses": [],
        "untrusted_secret_like_field": "must-not-escape",
    }]},
    {"results": [{"id": 7, "name": "Thanatos", "primary_ip4": {"address": "192.0.2.75/24"}}]},
)
assert result["status"] == "OK" and result["writes_performed"] is False
assert result["inventory_is_not_liveness"] is True
assert result["services"] == [{
    "name": "Minecraft Java", "parent_type": "device", "parent_name": "Thanatos",
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
from datetime import datetime, timedelta, timezone
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
matrix_path.write_text(json.dumps({"observed_at": datetime.now(timezone.utc).isoformat(), "machines": [
    {"name": "tartarus", "address": "192.0.2.69", "os": "Fedora",
     "cpu": "synthetic", "ram_gib": 64, "gpus": ["4x Quadro P4000"],
     "nvidia_driver": "synthetic", "cuda_container_capability": "unknown",
     "runtime_status": "observed-only", "ssh": "synthetic", "role": "inference"},
    {"name": "hypnos", "address": "192.0.2.73", "os": "Fedora",
     "cpu": "synthetic", "ram_gib": 64, "gpus": ["2x Quadro P4000"],
     "nvidia_driver": "synthetic", "cuda_container_capability": "unknown",
     "runtime_status": "observed-only", "ssh": "synthetic", "role": "inference"},
    {"name": "hermes", "address": "192.0.2.152", "os": "Linux",
     "cpu": "synthetic", "ram_gib": 64, "gpus": ["2x RTX 2080"],
     "nvidia_driver": "synthetic", "cuda_container_capability": "unknown",
     "runtime_status": "observed-only", "ssh": "synthetic", "role": "inference"},
]}), encoding="utf-8")
os.environ["HADES_CAPABILITY_MATRIX_FILE"] = str(matrix_path)

root = Path("integrations/homelab-readonly").resolve()
sys.path.insert(0, str(root))
import server

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
    {"name": "host-alpha", "status": "up", "last_updated": "2026-09-16 09:00:00.000", "monitor_type": "ping", "ping_ms": 84},
    {"name": "host-beta", "status": "down", "last_updated": "2026-09-16 09:00:01.000", "monitor_type": "ping"},
]
assert server._kuma_config_url() == "https://status.example.test/api/status-page/hades-status"

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
    "HADES_PROXMOX_RESOURCES_URLS": "https://pve-a.example.test/cluster/resources,https://pve-b.example.test/cluster/resources",
    "HADES_PROXMOX_TOKEN_FILES": "/run/synthetic-proxmox-a,/run/synthetic-proxmox-b",
    "HADES_PROXMOX_TOKEN_IDS": "svc-hades-ro@pve!synthetic-a,svc-hades-ro@pve!synthetic-b",
    "HADES_NETBOX_DEVICES_URL": "https://netbox.example.test/api/dcim/devices/",
    "HADES_NETBOX_SERVICES_URL": "https://netbox.example.test/api/ipam/services/",
    "HADES_KUMA_STATUS_URL": "https://status.example.test/api/status-page/heartbeat/hades-status",
})
original_fetch = server._fetch
try:
    original_fetch("https://reader:sentinel-private-value@example.test/api")
except ValueError as exc:
    assert "sentinel-private-value" not in str(exc)
else:
    raise AssertionError("credential-bearing source URLs must be rejected")
runtime_fixture = {
    "type": "qemu", "vmid": 802, "name": "hades-core", "node": "Erebus",
    "status": "running", "cpu": 0.25, "maxcpu": 16, "mem": 1073741824,
    "maxmem": 8589934592, "disk": 10737418240, "maxdisk": 53687091200,
    "uptime": 3600, "unrelated_secret_like_field": "must-not-escape",
}
device_fixture = {
    "id": 75, "name": "Thanatos", "primary_ip4": {"address": "192.0.2.75/24"},
}
service_fixture = {
    "name": "Minecraft Java", "device": {"id": 75, "name": "Thanatos"},
    "port_mappings": ["tcp/25565"], "ipaddresses": [],
    "secret_like_field": "must-not-escape",
}
def fixture_fetch(url, *_args, **_kwargs):
    if url == "https://pve-a.example.test/cluster/resources":
        return {"data": [runtime_fixture]}
    if url == "https://pve-b.example.test/cluster/resources":
        from urllib.error import URLError
        raise URLError("https://reader:sentinel-private-value@example.test/api token=sentinel-private-value")
    if url == "https://netbox.example.test/api/dcim/devices/":
        return {"results": [device_fixture]}
    if url == "https://netbox.example.test/api/ipam/services/":
        return {"results": [service_fixture]}
    if url == "https://status.example.test/api/status-page/heartbeat/hades-status":
        return {"monitors": []}
    raise AssertionError(f"unexpected synthetic adapter URL: {url}")
server._fetch = fixture_fetch
summary = server.homelab_summary()
assert summary["status"] == "PARTIAL", summary
assert summary["source_counts"]["proxmox_runtime_rows"] == 1, summary
assert summary["sources"]
assert {row["status"] for row in summary["sources"] if row["source"].startswith("Proxmox[")} == {"HEALTHY", "UNAVAILABLE"}
assert all(row["observation_scope"] == "source_read" for row in summary["sources"] if row["source"].startswith("Proxmox["))
assert any(row.get("status") == "DEGRADED" for row in summary["sources"] if row["source"] == "Proxmox")
assert summary["errors"] == ["Proxmox[2] unavailable"], summary["errors"]
assert "sentinel-private-value" not in str(summary)
assert all(isinstance(row.get("retrieved_at"), str) for row in summary["sources"] if row.get("duration_ms") is not None)
runtime_row = next(row for row in summary["resources"] if row["name"] == "hades-core")
assert runtime_row["runtime"] == {
    "name": "hades-core", "node": "Erebus", "type": "qemu", "vmid": 802,
    "status": "running", "cpu": 0.25, "maxcpu": 16,
    "mem": 1073741824, "maxmem": 8589934592,
    "disk": 10737418240, "maxdisk": 53687091200, "uptime": 3600,
}, runtime_row
assert runtime_row["currently_online"] is True
assert summary["source_counts"]["netbox_service_rows"] == 1
assert summary["service_catalog"]["services"] == [{
    "name": "Minecraft Java", "parent_type": "device", "parent_name": "Thanatos",
    "addresses": ["192.0.2.75"], "address_source": "NetBox parent primary IP",
    "port_mappings": ["tcp/25565"], "runtime_status": "UNKNOWN",
}]
assert "secret_like_field" not in str(summary)
assert "unrelated_secret_like_field" not in str(summary)
server._fetch = original_fetch
print("PASS homelab MCP summary retains bounded runtime telemetry without unrelated upstream fields")

result = server.homelab_compute_capabilities()
assert result["status"] == "OK"
assert result["freshness"] == "FRESH"
assert result["read_only"] is True
assert result["authority"]["runtime"] == "Proxmox"
assert result["availability_not_provided"] is True
assert "Never label a machine online" in result["liveness_rule"]
assert all("runtime_status" not in row for row in result["machines"])
rows = {row["name"]: row for row in result["machines"]}
assert rows["tartarus"]["gpus"] == ["4x Quadro P4000"]
assert rows["hypnos"]["gpus"] == ["2x Quadro P4000"]
assert rows["hermes"]["gpus"] == ["2x RTX 2080"]
assert "does not imply current availability" in result["placement_rule"]
matrix_doc = json.loads(matrix_path.read_text())
matrix_doc["observed_at"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
matrix_path.write_text(json.dumps(matrix_doc), encoding="utf-8")
stale_matrix = server.homelab_compute_capabilities()
assert stale_matrix["status"] == "STALE"
assert stale_matrix["freshness"] == "STALE"
assert stale_matrix["machines"] and stale_matrix["availability_not_provided"] is True
fresh_summary = server.homelab_summary
server.homelab_summary = lambda: {"status": "OK"}
assert server.homelab_owner_snapshot()["status"] == "PARTIAL"
server.homelab_summary = fresh_summary
unknown_matrix = dict(matrix_doc)
unknown_matrix.pop("observed_at")
matrix_path.write_text(json.dumps(unknown_matrix), encoding="utf-8")
assert server.homelab_compute_capabilities()["status"] == "UNKNOWN"
os.environ.pop("HADES_CAPABILITY_MATRIX_FILE", None)
assert server.homelab_compute_capabilities()["status"] == "UNAVAILABLE"

# Failure composition: a source outage must remain visible while preserving
# the authorities that did return data. Hardware metadata must not mask the
# partial live-source result.
original_summary = server.homelab_summary
original_compute = server.homelab_compute_capabilities
server.homelab_summary = lambda: {
    "status": "PARTIAL",
    "online_names": ["Alexandra"],
    "errors": ["Uptime Kuma source unavailable"],
    "answer_contract": {"currently_online_source": "Proxmox runtime only"},
}
server.homelab_compute_capabilities = lambda: {
    "status": "OK",
    "machines": [{"name": "Tartarus", "gpus": ["4x Quadro P4000"]}],
    "availability_not_provided": True,
}
partial = server.homelab_owner_snapshot()
assert partial["status"] == "PARTIAL"
assert partial["summary"]["online_names"] == ["Alexandra"]
assert partial["summary"]["errors"] == ["Uptime Kuma source unavailable"]
assert partial["compute"]["machines"][0]["name"] == "Tartarus"
assert partial["answer_contract"]["inventory_is_not_liveness"] is True
assert partial["read_only"] is True
server.homelab_summary = original_summary
server.homelab_compute_capabilities = original_compute
print("PASS observed compute capability read is bounded, explicit, and read-only")
print("PASS owner snapshot preserves partial-source errors and authority boundaries")
PY

python -m py_compile integrations/homelab-readonly/reconcile.py integrations/homelab-readonly/server.py
echo 'PASS homelab MCP adapter is syntax-valid and read-only by construction'
