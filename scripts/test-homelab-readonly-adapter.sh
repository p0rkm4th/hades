#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
import importlib.util
import sys
import os
import tempfile
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("integrations/homelab-readonly")
spec = importlib.util.spec_from_file_location("homelab_reconcile", root / "reconcile.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
result = module.summarize(
    {"data": [{"_hades_identity": "proxmox:pve-a:qemu:101", "type": "qemu", "vmid": 101, "name": "dinner-app", "node": "pve-a", "status": "running"}]},
    {"results": [{"id": 75, "name": "dinner-app", "planned_node": "Beta", "status": "active"}]},
    {"monitors": [{"id": 7, "name": "dinner-app", "status": "down", "last_updated": "2026-09-14T11:40:00+00:00"}]},
    now=now,
    identity_links={
        "proxmox:pve-a:qemu:101": "netbox:device:75",
        "kuma:monitor:7": "netbox:device:75",
    },
)
resource = result["resources"][0]
assert result["status"] == "PARTIAL"
assert result["online_names"] == ["dinner-app"]
assert result["source_counts"] == {
    "proxmox_runtime_rows": 1,
    "netbox_inventory_rows": 1,
    "kuma_monitor_rows": 1,
    "composed_resources": 1,
    "identity_unlinked_resources": 0,
}
assert result["availability_summary"][0]["name"] == "dinner-app"
assert result["availability_summary"][0]["status"] == "down"
assert result["availability_summary"][0]["freshness"] == "STALE"
assert result["answer_contract"]["writes_performed"] is False
assert resource["runtime"]["node"] == "pve-a"
assert resource["runtime_status"] == "running"
assert resource["currently_online"] is True
assert resource["inventory"]["planned_node"] == "Beta"
assert resource["availability"]["status"] == "down"
assert resource["availability_freshness"] == "STALE"
assert resource["conflicts"]
assert resource["identity"]["status"] == "LINKED"
assert resource["identity"]["canonical_id"] == "netbox:device:75"
assert result["identity_warnings"] == []
assert result["authority"]["runtime"] == "Proxmox"
vm_result = module.summarize(
    {"data": [{"type": "qemu", "vmid": 1802, "name": "hades-core", "node": "pve-main", "status": "running"}]},
    {"results": []},
    {"monitors": []},
)
vm_resource = vm_result["resources"][0]
assert vm_result["online_names"] == ["hades-core"]
assert vm_result["inventory_only_names"] == []
assert vm_resource["runtime"] == {
    "name": "hades-core", "node": "pve-main", "type": "qemu", "vmid": 1802, "status": "running"
}
assert vm_resource["inventory"] is None
assert vm_resource["currently_online"] is True
future = module.summarize(
    {"data": [{"_hades_identity": "proxmox:pve-a:qemu:102", "type": "qemu", "vmid": 102, "name": "clock-skewed", "node": "pve-a", "status": "running"}]},
    {"results": []},
    {"monitors": [{"id": 8, "name": "clock-skewed", "status": "up", "last_updated": "2026-09-14T12:05:00+00:00"}]},
    now=now,
)
assert future["status"] == "PARTIAL"
assert len(future["resources"]) == 2
assert any(row["availability_freshness"] == "UNKNOWN" for row in future["resources"])
assert future["identity_warnings"][0]["type"] == "SAME_NAME_NOT_LINKED"
contradictory = module.summarize(
    {"data": [{"_hades_identity": "proxmox:pve-a:qemu:103", "type": "qemu", "vmid": 103, "name": "worker", "node": "pve-a", "status": "running"}]},
    {"results": [{"id": 100, "name": "worker", "planned_node": "pve-b"}]},
    {"monitors": []},
    now=now,
    identity_links={"proxmox:pve-a:qemu:103": "netbox:device:100"},
)
assert len(contradictory["resources"]) == 1
assert contradictory["resources"][0]["identity"]["status"] == "LINKED"
assert contradictory["resources"][0]["conflicts"]
assert contradictory["status"] == "PARTIAL"
inventory_only = module.summarize(
    {"data": []},
    {"results": [{"id": 99, "name": "gpu-a"}]},
    None,
)
assert inventory_only["online_names"] == []
assert inventory_only["inventory_only_names"] == ["gpu-a"]
assert inventory_only["resources"][0]["runtime_status"] == "NOT_OBSERVED"
assert inventory_only["resources"][0]["currently_online"] is None
sys.path.insert(0, str(root.resolve()))
import config as homelab_config
with tempfile.TemporaryDirectory() as temp_dir:
    link_file = Path(temp_dir) / "links.json"
    link_file.write_text(json.dumps({"links": [
        {"source_identity": "proxmox:pve-a:qemu:101", "netbox_device_id": 75},
        {"source_identity": "kuma:monitor:7", "netbox_device_id": 75},
        {"source_identity": "inference:gpu-lane-a", "netbox_device_id": 75},
    ]}), encoding="utf-8")
    link_file.chmod(0o600)
    os.environ["HADES_HOMELAB_IDENTITY_LINKS_FILE"] = str(link_file)
    assert homelab_config.load_identity_links() == {
        "proxmox:pve-a:qemu:101": "netbox:device:75",
        "kuma:monitor:7": "netbox:device:75",
        "inference:gpu-lane-a": "netbox:device:75",
    }
    link_file.chmod(0o644)
    try:
        homelab_config.load_identity_links()
    except ValueError as exc:
        assert "mode 0600 or 0640" in str(exc)
    else:
        raise AssertionError("unsafe identity-link permissions were accepted")
    link_file.unlink()
    link_file.symlink_to(Path(temp_dir) / "target.json")
    try:
        homelab_config.load_identity_links()
    except ValueError as exc:
        assert "non-symlink" in str(exc)
    else:
        raise AssertionError("symlinked identity-link file was accepted")
    os.environ.pop("HADES_HOMELAB_IDENTITY_LINKS_FILE", None)
assert homelab_config.proxmox_source_ids((
    ("https://one.example.test/cluster/resources", "/token-a"),
    ("https://two.example.test/cluster/resources", "/token-b"),
)) == ("endpoint-1", "endpoint-2")
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
os.environ["HADES_INFERENCE_ENDPOINTS_JSON"] = json.dumps([{
    "id": "fast-lane-a", "url": "https://inference.example.test",
    "token_file": "/run/hades/inference.token",
}])
assert config.inference_endpoint_specs() == ({
    "id": "fast-lane-a", "provider": "ollama", "url": "https://inference.example.test",
    "token_file": "/run/hades/inference.token", "ca_file": "",
},)
os.environ["HADES_INFERENCE_ENDPOINTS_JSON"] = json.dumps([{
    "id": "fast-lane-a", "url": "http://inference.example.test",
    "token_file": "/run/hades/inference.token",
}])
try:
    config.inference_endpoint_specs()
except ValueError as exc:
    assert "require HTTPS" in str(exc)
else:
    raise AssertionError("inference credentials over HTTP were accepted")
os.environ["HADES_INFERENCE_ENDPOINTS_JSON"] = json.dumps([{
    "id": "fast-lane-a", "provider": [], "url": "https://inference.example.test",
}])
try:
    config.inference_endpoint_specs()
except ValueError as exc:
    assert "provider must be" in str(exc)
else:
    raise AssertionError("invalid inference provider kind was accepted")
os.environ["HADES_INFERENCE_ENDPOINTS_JSON"] = json.dumps([{
    "id": "fast-lane-a", "url": "https://user:password@inference.example.test",
}])
try:
    config.inference_endpoint_specs()
except ValueError as exc:
    assert "without credentials" in str(exc)
else:
    raise AssertionError("credential-bearing inference endpoint URL was accepted")
os.environ.pop("HADES_INFERENCE_ENDPOINTS_JSON", None)
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
os.environ.pop("HADES_PROXMOX_TOKEN_IDS", None)
try:
    config.proxmox_token_ids()
except ValueError as exc:
    assert "required when token files are configured" in str(exc)
else:
    raise AssertionError("Proxmox token files without token IDs must fail closed")
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
print("PASS Proxmox runtime exposes a synthetic guest without inventing a NetBox record")
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
    {"count": 1, "next": None, "results": [{
        "name": "Minecraft Java",
        "device": {"id": 7, "name": "test-game-host"},
        "port_mappings": ["TCP/25565", "udp/25565", "tcp/99999", "tcp/any"],
        "ipaddresses": [],
        "untrusted_secret_like_field": "must-not-escape",
    }]},
    {"results": [{"id": 7, "name": "test-game-host", "primary_ip4": {"address": "192.0.2.75/24"}}]},
)
assert result["status"] == "OK" and result["writes_performed"] is False
assert result["coverage"] == "COMPLETE"
assert result["records_returned"] == 1 and result["source_total"] == 1
assert result["inventory_is_not_liveness"] is True
assert result["services"] == [{
    "name": "Minecraft Java", "parent_type": "device", "parent_name": "test-game-host",
    "addresses": ["192.0.2.75"], "address_source": "NetBox parent primary IP",
    "port_mappings": ["tcp/25565", "udp/25565"], "runtime_status": "UNKNOWN",
}]
assert "untrusted_secret_like_field" not in str(result)
unmatched_parent = module.project_netbox_services(
    {"results": [{"name": "Minecraft Java", "device": {"id": 8, "name": "test-game-host"}}]},
    {"results": [{"id": 7, "name": "test-game-host", "primary_ip4": {"address": "192.0.2.75/24"}}]},
)
assert unmatched_parent["services"][0]["addresses"] == []
assert unmatched_parent["services"][0]["address_source"] is None
empty_services = module.project_netbox_services(
    {"count": 0, "next": None, "results": []}, {"results": []},
)
assert empty_services["status"] == "OK"
assert empty_services["coverage"] == "EMPTY"
assert empty_services["records_returned"] == 0
assert empty_services["source_total"] == 0
partial_services = module.project_netbox_services(
    {"count": 5, "next": "https://netbox.example.test/api/ipam/services/?offset=2", "results": [
        {"name": "service-a"}, {"name": "service-b"},
    ]}, {"results": []},
)
assert partial_services["coverage"] == "PARTIAL"
assert partial_services["truncated"] is True
unknown_coverage = module.project_netbox_services(
    {"results": [{"name": "service-a"}]}, {"results": []},
)
assert unknown_coverage["coverage"] == "UNKNOWN"
inconsistent_count = module.project_netbox_services(
    {"count": 0, "next": None, "results": [{"name": "unexpected-row"}]},
    {"results": []},
)
assert inconsistent_count["coverage"] == "PARTIAL"
print("PASS NetBox service projection joins parent address, validates protocol/ports, and never claims liveness")
PY

python3 - <<'PY'
import atexit
import json
import os
import shutil
import sys
import threading
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
    {"name": "gpu-a", "address": "192.0.2.69", "os": "Fedora",
     "cpu": "synthetic", "ram_gib": 64, "gpus": ["4x Synthetic GPU A"],
     "nvidia_driver": "synthetic", "cuda_container_capability": "unknown",
     "runtime_status": "observed-only", "ssh": "synthetic", "role": "inference"},
    {"name": "gpu-b", "address": "192.0.2.73", "os": "Fedora",
     "cpu": "synthetic", "ram_gib": 64, "gpus": ["2x Synthetic GPU B"],
     "nvidia_driver": "synthetic", "cuda_container_capability": "unknown",
     "runtime_status": "observed-only", "ssh": "synthetic", "role": "inference"},
    {"name": "gpu-c", "address": "192.0.2.152", "os": "Linux",
     "cpu": "synthetic", "ram_gib": 64, "gpus": ["2x Synthetic GPU C"],
     "nvidia_driver": "synthetic", "cuda_container_capability": "unknown",
     "runtime_status": "observed-only", "ssh": "synthetic", "role": "inference"},
]}), encoding="utf-8")
os.environ["HADES_CAPABILITY_MATRIX_FILE"] = str(matrix_path)

root = Path("integrations/homelab-readonly").resolve()
sys.path.insert(0, str(root))
import server
assert "homelab_inference_inventory" in {tool.name for tool in server.TOOLS}

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
    {"id": 7, "name": "host-alpha", "status": "up", "last_updated": "2026-09-16 09:00:00.000", "monitor_type": "ping", "ping_ms": 84},
    {"id": 8, "name": "host-beta", "status": "down", "last_updated": "2026-09-16 09:00:01.000", "monitor_type": "ping"},
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
assert latency_result["availability_summary"][0] == {
    "name": "Router ping", "status": "up", "freshness": "FRESH",
    "source_identity": "kuma:unidentified:0", "ping_ms": 84,
}
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
    "type": "qemu", "vmid": 1802, "name": "hades-core", "node": "pve-main",
    "status": "running", "cpu": 0.25, "maxcpu": 16, "mem": 1073741824,
    "maxmem": 8589934592, "disk": 10737418240, "maxdisk": 53687091200,
    "uptime": 3600, "unrelated_secret_like_field": "must-not-escape",
}
extra_runtime_fixtures = [
    {"type": "qemu", "vmid": 900 + index, "name": f"worker-{index}",
     "node": "synthetic-pve", "status": "running"}
    for index in range(1, 6)
]
device_fixture = {
    "id": 75, "name": "test-game-host", "primary_ip4": {"address": "192.0.2.75/24"},
}
service_fixture = {
    "name": "Minecraft Java", "device": {"id": 75, "name": "test-game-host"},
    "port_mappings": ["tcp/25565"], "ipaddresses": [],
    "secret_like_field": "must-not-escape",
}
proxmox_barrier = threading.Barrier(2)
def fixture_fetch(url, *_args, **_kwargs):
    if url == "https://pve-a.example.test/cluster/resources":
        proxmox_barrier.wait(timeout=1.0)
        return {"data": [runtime_fixture, *extra_runtime_fixtures]}
    if url == "https://pve-b.example.test/cluster/resources":
        proxmox_barrier.wait(timeout=1.0)
        from urllib.error import URLError
        raise URLError("https://reader:sentinel-private-value@example.test/api token=sentinel-private-value")
    if url == "https://netbox.example.test/api/dcim/devices/":
        return {"results": [device_fixture]}
    if url == "https://netbox.example.test/api/ipam/services/":
        return {"count": 1, "next": None, "results": [service_fixture]}
    if url == "https://status.example.test/api/status-page/heartbeat/hades-status":
        return {"monitors": []}
    raise AssertionError(f"unexpected synthetic adapter URL: {url}")
server._fetch = fixture_fetch
summary = server.homelab_summary()
assert summary["status"] == "PARTIAL", summary
assert summary["source_counts"]["proxmox_runtime_rows"] == 6, summary
assert len(summary["resources"]) >= 6 and "resources_truncated" not in summary, summary
assert summary["sources"]
assert {row["status"] for row in summary["sources"] if row["source"].startswith("Proxmox[")} == {"HEALTHY", "UNAVAILABLE"}
assert all(row["observation_scope"] == "source_read" for row in summary["sources"] if row["source"].startswith("Proxmox["))
assert any(row.get("status") == "DEGRADED" for row in summary["sources"] if row["source"] == "Proxmox")
assert summary["errors"] == ["Proxmox[2] unavailable"], summary["errors"]
assert "sentinel-private-value" not in str(summary)
assert all(isinstance(row.get("retrieved_at"), str) for row in summary["sources"] if row.get("duration_ms") is not None)
runtime_row = next(row for row in summary["resources"] if row["name"] == "hades-core")
assert runtime_row["runtime"] == {
    "name": "hades-core", "node": "pve-main", "type": "qemu", "vmid": 1802,
    "status": "running", "cpu": 0.25, "maxcpu": 16,
    "mem": 1073741824, "maxmem": 8589934592,
    "disk": 10737418240, "maxdisk": 53687091200, "uptime": 3600,
}, runtime_row
assert runtime_row["currently_online"] is True
assert summary["source_counts"]["netbox_service_rows"] == 1
assert summary["service_catalog"]["coverage"] == "COMPLETE"
assert summary["service_catalog"]["services"] == [{
    "name": "Minecraft Java", "parent_type": "device", "parent_name": "test-game-host",
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
assert rows["gpu-a"]["gpus"] == ["4x Synthetic GPU A"]
assert rows["gpu-b"]["gpus"] == ["2x Synthetic GPU B"]
assert rows["gpu-c"]["gpus"] == ["2x Synthetic GPU C"]
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
    "online_names": ["pve-a"],
    "errors": ["Uptime Kuma source unavailable"],
    "answer_contract": {"currently_online_source": "Proxmox runtime only"},
}
server.homelab_compute_capabilities = lambda: {
    "status": "OK",
    "machines": [{"name": "GPU A", "gpus": ["4x Synthetic GPU A"]}],
    "availability_not_provided": True,
}
partial = server.homelab_owner_snapshot()
assert partial["status"] == "PARTIAL"
assert partial["summary"]["online_names"] == ["pve-a"]
assert partial["summary"]["errors"] == ["Uptime Kuma source unavailable"]
assert partial["compute"]["machines"][0]["name"] == "GPU A"
assert partial["answer_contract"]["inventory_is_not_liveness"] is True
assert partial["read_only"] is True
server.homelab_summary = original_summary
server.homelab_compute_capabilities = original_compute

# Provider-native inference reads must retain current loaded-model state and
# source identity without treating catalog size as free GPU capacity.
identity_file = matrix_dir / "identity-links.json"
identity_file.write_text(json.dumps({"links": [
    {"source_identity": "inference:gpu-lane-a", "netbox_device_id": 75},
]}), encoding="utf-8")
identity_file.chmod(0o600)
os.environ["HADES_HOMELAB_IDENTITY_LINKS_FILE"] = str(identity_file)
os.environ["HADES_INFERENCE_ENDPOINTS_JSON"] = json.dumps([{
    "id": "gpu-lane-a", "url": "http://inference.example.test",
}])
inference_calls = []
def inference_fetch(url, token_file="", ca_file="", proxmox_token_id="", timeout_seconds=10):
    inference_calls.append((url, timeout_seconds))
    if url.endswith("/api/tags"):
        return {"models": [{
            "name": "sample:small", "modified_at": "2026-10-01T00:00:00Z",
            "size": 1024, "digest": "synthetic-digest",
            "details": {"family": "sample", "parameter_size": "8B", "quantization_level": "Q4"},
        }]}
    if url.endswith("/api/ps"):
        return {"models": [{
            "name": "sample:small", "size": 1024, "size_vram": 768,
            "expires_at": "2026-10-01T00:10:00Z",
        }]}
    raise AssertionError("unexpected inference API path")
server._fetch = inference_fetch
inference = server.homelab_inference_inventory()
assert inference["status"] == "READABLE", (inference, inference_calls)
endpoint = inference["endpoints"][0]
assert endpoint["source_identity"] == "inference:gpu-lane-a"
assert endpoint["node_identity"] == "netbox:device:75"
assert endpoint["identity_status"] == "LINKED"
assert endpoint["catalog_freshness"] == "LIVE"
assert endpoint["models"][0]["name"] == "sample:small"
assert endpoint["loaded_models"][0]["size_vram_bytes"] == 768, inference
os.environ["HADES_NETBOX_URL"] = "https://netbox.example.test"
def netbox_device_fetch(url, *args, **kwargs):
    assert url.endswith("/api/dcim/devices/75/")
    return {"id": 75, "name": "GPU A"}
server._fetch = netbox_device_fetch
device_labels = server.resolve_inference_node_labels(inference)
assert device_labels == {"netbox:device:75": "GPU A"}
summary_names = {"resources": [{
    "identity": {"canonical_id": "netbox:device:75"},
    "inventory": {"name": "GPU A"},
}]}
where_answer = server.format_inference_inventory_response(
    "Where's sample:small?", inference, summary_names,
)
assert "sample:small is listed by GPU A" in where_answer, where_answer
assert "Provider reports it resident on GPU A" in where_answer, where_answer
assert "does not prove GPU execution" in where_answer, where_answer
summary_names["capability_freshness"] = "FRESH"
summary_names["capability_machines"] = [{
    "name": "GPU A", "role": "deep inference lane",
    "gpus": [{"model": "synthetic accelerator", "count": 4}],
}]
placement_answer = server.format_inference_inventory_response(
    "Where should I run another model?", inference, summary_names,
)
assert "Responding inference endpoints: GPU A" in placement_answer, placement_answer
assert "recorded role: deep inference lane" in placement_answer, placement_answer
assert "4 × synthetic accelerator" in placement_answer, placement_answer
assert "loaded: sample:small" in placement_answer, placement_answer
assert "can't rank a host" in placement_answer, placement_answer
assert "can't confirm capacity or fit" in placement_answer, placement_answer
assert "candidate to evaluate" not in placement_answer, placement_answer
stale_summary = {
    **summary_names,
    "capability_freshness": "STALE",
}
stale_placement_answer = server.format_inference_inventory_response(
    "Where should I run another model?", inference, stale_summary,
)
assert "Hardware role/capability inventory is stale" in stale_placement_answer, stale_placement_answer
assert "recorded role:" not in stale_placement_answer, stale_placement_answer
assert "GPU A" in stale_placement_answer and "can't rank a host" in stale_placement_answer
node_activity_answer = server.format_inference_inventory_response(
    "What's GPU A doing right now?", inference, summary_names,
)
assert "inference endpoint linked to GPU A is responding" in node_activity_answer, node_activity_answer
assert "Provider-reported residency: sample:small" in node_activity_answer, node_activity_answer
assert "does not prove GPU execution" in node_activity_answer, node_activity_answer
assert "does not measure host CPU/GPU utilization" in node_activity_answer, node_activity_answer
proxmox_node_summary = {"resources": [{
    "name": "Runtime Node B", "runtime_status": "online",
    "inventory": {"name": "Runtime Node B", "role": "virtualization host"},
    "conflicts": ["NetBox intended node differs from Proxmox runtime node"],
}]}
node_without_inference = server.format_inference_inventory_response(
    "What's Runtime Node B doing?",
    {"status": "NOT_CONFIGURED", "endpoints": []}, proxmox_node_summary,
)
assert "Proxmox currently reports Runtime Node B online" in node_without_inference, node_without_inference
assert "No linked inference endpoint" in node_without_inference
assert "Source disagreement" in node_without_inference, node_without_inference
physical_node_summary = {"resources": [{
    "name": "Physical Node C", "runtime_status": "NOT_OBSERVED",
    "inventory": {"name": "Physical Node C", "role": "compute"},
}]}
unknown_physical_node = server.format_inference_inventory_response(
    "What's Physical Node C doing?",
    {"status": "NOT_CONFIGURED", "endpoints": []}, physical_node_summary,
)
assert "can't say whether it's online" in unknown_physical_node, unknown_physical_node
assert "NetBox lists its role as compute" in unknown_physical_node, unknown_physical_node
summary_answer = server.format_inference_inventory_response(
    "What models are available?", inference, summary_names,
)
assert "Installed: sample:small" in summary_answer, summary_answer
assert "do not prove GPU execution" in summary_answer
ai_available_answer = server.format_inference_inventory_response(
    "Can we use the AI thing right now?", inference, summary_names,
)
assert "All 1 configured AI provider checks are responding to catalog reads" in ai_available_answer, ai_available_answer
assert "I haven't tested a generation" in ai_available_answer, ai_available_answer
partial_ai_inventory = {
    "status": "PARTIAL",
    "endpoints": [inference["endpoints"][0], {
        "source_identity": "inference:offline-provider", "status": "SOURCE_UNAVAILABLE",
    }],
}
partial_ai_answer = server.format_inference_inventory_response(
    "Is the AI available?", partial_ai_inventory, summary_names,
)
assert "1 of 2 configured AI provider checks are responding" in partial_ai_answer, partial_ai_answer
assert "1 could not be verified" in partial_ai_answer, partial_ai_answer
assert "can't confirm the AI can answer a prompt right now" in partial_ai_answer, partial_ai_answer
failed_ai_answer = server.format_inference_inventory_response(
    "Can we use AI right now?", {
        "status": "SOURCE_UNAVAILABLE",
        "endpoints": [{"source_identity": "inference:offline-provider", "status": "SOURCE_UNAVAILABLE"}],
    }, summary_names,
)
assert "none of the configured provider catalog checks succeeded" in failed_ai_answer, failed_ai_answer
assert server._bounded_text("model-alpha\nInjected") == "model-alpha Injected"
assert all(timeout == 4 for _, timeout in inference_calls)
assert [url.endswith("/api/tags") for url, _ in inference_calls] == [True, False]

# OpenAI-compatible endpoints expose a configured model catalog but do not
# define a standard current-residency API. Never present the catalog as loaded.
os.environ["HADES_INFERENCE_ENDPOINTS_JSON"] = json.dumps([{
    "id": "fast-lane-b", "provider": "openai-compatible",
    "url": "http://inference.example.test",
}])
def compatible_fetch(url, *args, **kwargs):
    assert url.endswith("/v1/models")
    return {"data": [{"id": "sample:fast"}]}
server._fetch = compatible_fetch
compatible = server.homelab_inference_inventory()
assert compatible["status"] == "READABLE"
compatible_endpoint = compatible["endpoints"][0]
assert compatible_endpoint["provider"] == "openai-compatible"
assert compatible_endpoint["models"][0]["name"] == "sample:fast"
assert compatible_endpoint["loaded_status"] == "UNSUPPORTED"
assert compatible_endpoint["loaded_models"] == []
compatible_answer = server.format_inference_inventory_response(
    "What models are available?", compatible, {},
)
assert "sample:fast" in compatible_answer
assert "partly unavailable" in compatible_answer
assert "No models are currently reported as loaded" not in compatible_answer
gpu_answer = server.format_inference_inventory_response(
    "Which GPUs are free?", compatible, {},
)
assert "can't verify which GPUs are free right now" in gpu_answer, gpu_answer
assert "empty model-residency report does not establish available capacity" in gpu_answer
for question in ("Where should I run another model?", "Can this handle a 20 GB model?"):
    answer = server.format_inference_inventory_response(question, compatible, {})
    assert "can't recommend an inference host" in answer, (question, answer)

os.environ["HADES_INFERENCE_ENDPOINTS_JSON"] = json.dumps([{
    "id": "gpu-lane-a", "url": "http://inference.example.test",
}])
def partial_inference_fetch(url, *args, **kwargs):
    if url.endswith("/api/tags"):
        return {"models": [{"name": "sample:small", "size": 1024}]}
    raise TimeoutError("synthetic source timeout")
server._fetch = partial_inference_fetch
partial_inference = server.homelab_inference_inventory()
assert partial_inference["status"] == "PARTIAL", partial_inference
assert partial_inference["endpoints"][0]["status"] == "PARTIAL"
assert partial_inference["endpoints"][0]["loaded_status"] == "TIMEOUT"
assert partial_inference["endpoints"][0]["models"]
partial_placement_answer = server.format_inference_inventory_response(
    "Where should I run another model?", partial_inference, summary_names,
)
assert "GPU A" in partial_placement_answer, partial_placement_answer
assert "provider read is partial" in partial_placement_answer, partial_placement_answer
assert "catalog lists: sample:small" in partial_placement_answer, partial_placement_answer
assert "loaded-model state unavailable" in partial_placement_answer, partial_placement_answer
assert "can't rank a host" in partial_placement_answer, partial_placement_answer
assert "loaded: sample:small" not in partial_placement_answer, partial_placement_answer

def unavailable_inference_fetch(_url, *args, **kwargs):
    raise OSError("synthetic private-value-must-not-escape")
server._fetch = unavailable_inference_fetch
unavailable_inference = server.homelab_inference_inventory()
assert unavailable_inference["status"] == "SOURCE_UNAVAILABLE"
assert unavailable_inference["endpoints"][0]["error"] == "SOURCE_IO_ERROR"
assert "private-value-must-not-escape" not in json.dumps(unavailable_inference)

os.environ.pop("HADES_HOMELAB_IDENTITY_LINKS_FILE", None)
os.environ.pop("HADES_INFERENCE_ENDPOINTS_JSON", None)
os.environ.pop("HADES_NETBOX_URL", None)
assert server.homelab_inference_inventory()["status"] == "NOT_CONFIGURED"
print("PASS provider-native model catalog and residency reads preserve identity and freshness")
print("PASS inference endpoint partial failure preserves catalog with explicit loaded-state uncertainty")
print("PASS observed compute capability read is bounded, explicit, and read-only")
print("PASS owner snapshot preserves partial-source errors and authority boundaries")

# Proxmox backup status is a bounded, owner-gated read of vzdump job config
# and archived task history. It must not leak raw UPIDs, usernames, or errors.
backup_token = matrix_dir / "proxmox.token"
backup_token.write_text("synthetic-secret-token", encoding="utf-8")
os.chmod(backup_token, 0o600)
os.environ.update({
    "HADES_PROXMOX_RESOURCES_URLS": "https://pve.example.test/api2/json/cluster/resources",
    "HADES_PROXMOX_TOKEN_FILES": str(backup_token),
    "HADES_PROXMOX_TOKEN_IDS": "svc-hades-ro@pve!test",
    "HADES_PROXMOX_SOURCE_IDS": "pve-test",
})
assert "homelab_backup_status" in {tool.name for tool in server.TOOLS}
def backup_fetch(url, *_args, **_kwargs):
    if url.endswith("/cluster/backup"):
        return {"data": [{"id": "nightly", "schedule": "02:00", "storage": "backup-store", "enabled": 1}]}
    if url.endswith("/cluster/resources"):
        return {"data": [{"type": "node", "node": "node-a"}]}
    if "/nodes/node-a/tasks?" in url:
        return {"data": [
            {"id": "802", "status": "OK", "endtime": 1790900000,
             "upid": "UPID:private-user:secret"},
            {"id": "803", "status": "ERROR: private failure detail", "starttime": 1790800000,
             "user": "private-user@pam"},
        ]}
    raise AssertionError("unexpected Proxmox backup URL")
server._fetch = backup_fetch
backup_report = server.homelab_backup_status()
assert backup_report["status"] == "READABLE", backup_report
backup_endpoint = backup_report["endpoints"][0]
assert backup_endpoint["jobs_status"] == "HEALTHY"
assert backup_endpoint["tasks_status"] == "HEALTHY"
assert backup_endpoint["tasks"][0]["status"] == "OK"
assert backup_endpoint["tasks"][1]["status"] == "ERROR"
assert "UPID:" not in json.dumps(backup_report)
assert "private-user" not in json.dumps(backup_report)
assert "private failure detail" not in json.dumps(backup_report)
backup_text = server.format_homelab_backup_status(backup_report)
assert "doesn't verify backup contents" in backup_text
assert "private" not in backup_text

def empty_backup_fetch(url, *_args, **_kwargs):
    if url.endswith("/cluster/backup"):
        return {"data": []}
    if url.endswith("/cluster/resources"):
        return {"data": [{"type": "node", "node": "node-a"}]}
    if "/nodes/node-a/tasks?" in url:
        return {"data": []}
    raise AssertionError("unexpected Proxmox empty-backup URL")
server._fetch = empty_backup_fetch
empty_backup = server.homelab_backup_status()
assert empty_backup["status"] == "READABLE"
empty_text = server.format_homelab_backup_status(empty_backup)
assert "no configured vzdump jobs" in empty_text
assert "No archived vzdump task" in empty_text
assert "backup contents" in empty_text
assert "everything is backed up" not in empty_text.casefold()

def partial_backup_fetch(url, *_args, **_kwargs):
    if url.endswith("/cluster/backup"):
        raise PermissionError("synthetic-token-secret-must-not-escape")
    if url.endswith("/cluster/resources"):
        return {"data": [{"type": "node", "node": "node-a"}, {"type": "node", "node": "node-b"}]}
    if "/nodes/node-a/tasks?" in url:
        return {"data": []}
    raise TimeoutError("synthetic-timeout-secret-must-not-escape")
server._fetch = partial_backup_fetch
partial_backup = server.homelab_backup_status()
assert partial_backup["status"] == "PARTIAL", partial_backup
partial_endpoint = partial_backup["endpoints"][0]
assert partial_endpoint["jobs_status"] == "UNAVAILABLE"
assert partial_endpoint["tasks_status"] == "PARTIAL"
assert "synthetic-token-secret" not in json.dumps(partial_backup)
assert "synthetic-timeout-secret" not in json.dumps(partial_backup)
print("PASS Proxmox backup read bounds and sanitizes configured vzdump jobs and task outcomes")
print("PASS Proxmox backup partial-source failure preserves available evidence without leaking errors")
PY

python -m py_compile integrations/homelab-readonly/reconcile.py integrations/homelab-readonly/server.py
echo 'PASS homelab MCP adapter is syntax-valid and read-only by construction'
