#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import importlib.util
import os

spec = importlib.util.spec_from_file_location("control", "integrations/homelab-control/control.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

os.environ["HADES_PROXMOX_CONTROL_NODES"] = "Erebus"
os.environ["HADES_PROXMOX_TEMPLATE_MAP"] = "palworld:9100,minecraft:9101"

assert module.inspect_templates() == {
    "status": "READY",
    "templates": ["minecraft", "palworld"],
    "approved_nodes": ["Erebus"],
    "writes_performed": False,
}

preview = module.provision_guest(
    "palworld", {"node": "Erebus", "vmid": 9200},
    name="palworld-home", owner_confirmed=False,
)
assert preview["status"] == "CONFIRMATION_REQUIRED"
assert preview["writes_performed"] is False

for bad in (
    {"node": "Alexandra", "vmid": 9200},
    {"node": "Erebus", "vmid": 9200, "extra": True},
):
    result = module.provision_guest("palworld", bad, name="x", owner_confirmed=True)
    assert result["status"] == "FAILED"
    assert result["writes_performed"] is False

too_large = module.provision_guest(
    "palworld", {"node": "Erebus", "vmid": 9200},
    name="x", cores=17, owner_confirmed=True,
)
assert too_large["status"] == "FAILED"
assert too_large["writes_performed"] is False

unknown = module.provision_guest(
    "factorio", {"node": "Erebus", "vmid": 9200},
    name="x", owner_confirmed=True,
)
assert unknown == {
    "status": "FAILED",
    "error": "server template is not approved",
    "writes_performed": False,
}

# Managed-guest lifecycle is fail-closed and bounded to the approved pool/range.
original_request = module._request
requests = []
state = {"status": "stopped", "deleted": False}

def fake_request(path, method="GET", params=None):
    requests.append((path, method, params))
    if path == "pools/hades-managed":
        return {"data": {"members": [{"type": "qemu", "node": "Erebus", "vmid": 9200}, {"type": "qemu", "node": "Erebus", "vmid": 853}]}}
    if path in {"nodes/Erebus/qemu/9200/status/current", "nodes/Erebus/qemu/853/status/current"}:
        return {"data": {"status": state["status"]}}
    if path == "nodes/Erebus/qemu/9200/config":
        return {"data": {"name": "test-sandbox", "tags": "hades-managed"}}
    if path == "nodes/Erebus/qemu/853/config":
        return {"data": {"name": "template", "template": 1, "tags": "hades-managed"}}
    if path.endswith("/status/start"):
        state["status"] = "running"
        return {"data": "UPID:test-start"}
    if path.endswith("/status/stop"):
        state["status"] = "stopped"
        return {"data": "UPID:test-stop"}
    if path.endswith("/status/reboot"):
        state["status"] = "running"
        return {"data": "UPID:test-reboot"}
    if path.endswith("/9200") and method == "DELETE":
        state["deleted"] = True
        return {"data": "UPID:test-delete"}
    if path.startswith("nodes/Erebus/tasks/"):
        return {"data": {"status": "stopped", "exitstatus": "OK"}}
    raise AssertionError((path, method, params))

module._request = fake_request
listed = module.list_managed_guests()
assert listed["status"] == "READY"
assert listed["writes_performed"] is False
assert len(listed["guests"]) == 1
assert listed["guests"][0]["vmid"] == 9200
assert listed["guests"][0]["name"] == "test-sandbox"
start_result = module.manage_guest({"node": "Erebus", "vmid": 9200}, "start", owner_confirmed=False)
assert start_result["status"] == "SUCCEEDED", start_result
delete_preview = module.manage_guest({"node": "Erebus", "vmid": 9200}, "delete", owner_confirmed=False)
assert delete_preview["status"] == "CONFIRMATION_REQUIRED", delete_preview
template_result = module.manage_guest({"node": "Erebus", "vmid": 853}, "status")
assert template_result["status"] == "FAILED", template_result
stop_result = module.manage_guest({"node": "Erebus", "vmid": 9200}, "stop", owner_confirmed=True)
assert stop_result["status"] == "SUCCEEDED", stop_result
assert module.manage_guest({"node": "Erebus", "vmid": 9200}, "bogus")["status"] == "FAILED"
module._request = original_request

print("PASS owner-confirmed bounded Proxmox provisioning contract")
print("PASS exact node/template/resource validation and fail-closed behavior")
print("PASS managed-guest listing and bounded lifecycle confirmation contract")
PY
