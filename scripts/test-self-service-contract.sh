#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from integrations.self_service import ConstrainedProvisioner, SelfServicePolicy, WorkloadRequest

owner = "synthetic-owner"
household_a = "synthetic-household-a"
policy = SelfServicePolicy()

preview = policy.plan(owner, "minecraft-1", "minecraft", "family-minecraft", shared_with=(household_a,))
assert preview["status"] == "PREVIEW" and preview["confirmation_required"]
request = WorkloadRequest(**preview["request"])
assert policy.confirm(household_a, request)["status"] == "DENIED"
ready = policy.confirm(owner, request)
assert ready["status"] == "READY_FOR_CONSTRAINED_PROVISIONER"
assert policy.can_manage(owner, "minecraft-1")
assert policy.can_manage(household_a, "minecraft-1")
assert not policy.can_manage("synthetic-household-b", "minecraft-1")

assert policy.plan(owner, "bad-1", "arbitrary-vm", "x")["status"] == "FAILED"
assert policy.plan(owner, "bad-2", "minecraft", "x", shared_with=("/root",))["status"] == "FAILED"
assert policy.plan(owner, "duplicate", "minecraft", "x")["status"] == "PREVIEW"
duplicate = policy.plan(owner, "duplicate", "minecraft", "x")["status"]
assert duplicate == "PREVIEW"  # planning is side-effect free until confirmation

limited = SelfServicePolicy({"max_workloads": 1, "max_cores": 4, "max_memory_mib": 8192, "max_disk_gib": 40})
first = limited.plan(owner, "one", "minecraft", "one")
limited.confirm(owner, WorkloadRequest(**first["request"]))
assert limited.plan(owner, "two", "minecraft", "two")["error"] == "workload quota exceeded"

assert ready["writes_performed"] is False

calls = []
def fake_executor(template, **kwargs):
    calls.append((template, kwargs))
    return {"status": "SUCCEEDED", "reconciled": True, "canonical_source": "synthetic-proxmox", "writes_performed": True}

executor = ConstrainedProvisioner(policy, fake_executor, {"minecraft": {"node": "Erebus", "vmid": 9201}})
assert executor.provision(household_a, "minecraft-1")["status"] == "DENIED"
result = executor.provision(owner, "minecraft-1")
assert result["status"] == "SUCCEEDED" and result["reconciled"]
assert calls[0][0] == "minecraft" and calls[0][1]["target"] == {"node": "Erebus", "vmid": 9201}
assert executor.provision(owner, "minecraft-1")["status"] == "SUCCEEDED"
assert len(calls) == 1

unknown = ConstrainedProvisioner(policy, lambda *_args, **_kwargs: {"status": "OUTCOME UNKNOWN", "writes_performed": True}, {"minecraft": {"node": "Erebus", "vmid": 9202}})
assert unknown.provision(owner, "minecraft-1")["status"] == "OUTCOME UNKNOWN"
assert unknown.provision(owner, "minecraft-1")["status"] == "OUTCOME UNKNOWN"  # unknown is not retried blindly
assert unknown.provision(owner, "missing")["status"] == "FAILED"

print("PASS approved-template preview and owner confirmation contract")
print("PASS ownership, sharing, quotas, idempotent planning, and fail-closed validation")
print("PASS constrained placement, owner-only execution, canonical result, and idempotency boundary")
print("PASS no Proxmox contact or writes in self-service policy tests")
PY
