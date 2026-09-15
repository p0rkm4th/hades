#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import importlib.util

spec = importlib.util.spec_from_file_location("control", "integrations/homelab-readonly/control.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

runtime = {"node": "Alexandra", "vmid": 101, "status": "running"}
target = {"node": "Alexandra", "vmid": 101}

gated = module.build_control_preview("restart_guest", target, runtime)
assert gated["status"] == "OWNER_GATED"
assert gated["writes_performed"] is False
ready_without_confirmation = module.build_control_preview("restart_guest", target, runtime, owner_authorized=True)
assert ready_without_confirmation["status"] == "PREVIEW"
plan = module.build_control_preview("restart_guest", target, runtime, owner_authorized=True, confirm=True)
assert plan["status"] == "READY_TO_EXECUTE"
assert plan["canonical_source"] == "Proxmox"

success = module.reconcile_control_outcome(plan, {"node": "Alexandra", "vmid": 101, "status": "running"}, transport_outcome="UNKNOWN")
assert success == {"status": "SUCCEEDED", "canonical_source": "Proxmox", "reconciled": True}
failed = module.reconcile_control_outcome(plan, {"node": "Alexandra", "vmid": 101, "status": "running"}, transport_outcome="FAILED")
assert failed["status"] == "SUCCEEDED"  # canonical read-back wins after a lost response
unknown = module.reconcile_control_outcome(plan, None, transport_outcome="UNKNOWN")
assert unknown["status"] == "OUTCOME UNKNOWN" and unknown["retry"] is False

for operation, bad_target, bad_runtime in (
    ("shell", target, runtime),
    ("stop_guest", {"node": "Alexandra", "vmid": 101}, {**runtime, "status": "stopped"}),
    ("restart_guest", {"node": "Other", "vmid": 101}, runtime),
    ("restart_guest", {"node": "Alexandra", "vmid": True}, runtime),
):
    result = module.build_control_preview(operation, bad_target, bad_runtime, owner_authorized=True, confirm=True)
    assert result["status"] == "FAILED", (operation, result)

print("PASS exact-target Proxmox control preview and owner/confirmation gates")
print("PASS homelab control has no executor, shell, Docker, or network authority")
print("PASS canonical read-back classifies success, failure, and unknown without retry")
PY
