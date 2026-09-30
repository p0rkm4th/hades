#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import json
import tempfile
from pathlib import Path

from integrations.self_service.registry import WorkloadRegistry

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "workloads.json"
    registry = WorkloadRegistry(str(path))
    assert registry.register("erebus-900", owner="synthetic-owner", node="erebus", vmid=900, template="linux-sandbox", name="sandbox")["status"] == "READY"
    assert [item["resource_id"] for item in registry.list_for("synthetic-owner")] == ["erebus-900"]
    assert registry.list_for("synthetic-household-a") == []
    assert registry.grant("synthetic-owner", "erebus-900", "synthetic-household-a")["status"] == "READY"
    assert registry.can_manage("synthetic-household-a", "erebus-900")
    assert registry.grant("synthetic-household-a", "erebus-900", "synthetic-household-b")["status"] == "DENIED"
    assert registry.revoke("synthetic-owner", "erebus-900", "synthetic-household-a")["status"] == "READY"
    assert not registry.can_manage("synthetic-household-a", "erebus-900")
    assert registry.remove("synthetic-household-a", "erebus-900")["status"] == "DENIED"
    assert registry.remove("synthetic-owner", "erebus-900")["status"] == "READY"
    assert registry.list_for("synthetic-owner") == []
    assert path.stat().st_mode & 0o077 == 0
    json.loads(path.read_text())

print("PASS durable workload ownership and explicit sharing registry")
print("PASS operation-time revocation and owner-only grant management")
print("PASS registry contains authorization metadata only and is private")
PY
