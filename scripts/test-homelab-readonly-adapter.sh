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

HADES_CAPABILITY_MATRIX_FILE="$(pwd)/../hades-infra/inventory/capability-matrix.yaml" \
  /opt/hermes-agent/venv/bin/python - <<'PY'
import os
import sys
from pathlib import Path

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
        "7": [{"status": 1, "time": "2026-09-16 09:00:00.000"}],
        "8": [{"status": 0, "time": "2026-09-16 09:00:01.000"}],
    },
})
assert kuma["monitors"] == [
    {"name": "host-alpha", "status": "up", "last_updated": "2026-09-16 09:00:00.000"},
    {"name": "host-beta", "status": "down", "last_updated": "2026-09-16 09:00:01.000"},
]
assert server._kuma_config_url() == "https://status.example.test/api/status-page/hades-status"

result = server.homelab_compute_capabilities()
assert result["status"] == "OK"
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
