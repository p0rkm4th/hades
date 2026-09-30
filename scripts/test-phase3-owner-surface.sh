#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python - "$repo_root" <<'PY'
import ast
import os
import re
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from integrations.automation.phase3_self_service import (
    Phase3Authority,
    Phase3Catalog,
    Phase3Service,
    Phase3Store,
)

source = (root / "hermes/sitecustomize.py").read_text(encoding="utf-8")
tree = ast.parse(source)
names = {
    "_hades_phase3_owner_response",
    "_hades_phase3_template_name",
    "_hades_phase3_inventory",
    "_hades_phase3_response",
}
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
assert {node.name for node in functions} == names
namespace = {
    "os": os,
    "re": re,
}
exec(compile(ast.Module(body=functions, type_ignores=[]), "sitecustomize.py", "exec"), namespace)

owner = "synthetic-owner-subject"
other = "synthetic-household-subject"
records = [
    {
        "automation_id": "private-record-id-1",
        "template_type": "low-inventory-summary",
        "owner_subject_id": owner,
        "interval_minutes": 10080,
        "enabled": True,
        "status": "STAGED",
        "resource_scope": ["grocy.household"],
    },
    {
        "automation_id": "private-record-id-2",
        "template_type": "low-inventory-summary",
        "owner_subject_id": other,
        "interval_minutes": 10080,
        "enabled": True,
        "status": "STAGED",
        "resource_scope": ["grocy.household"],
    },
]

class Store:
    def __init__(self):
        self.pending = None
        self.disabled = None
    def pending_get(self, _key, _subject):
        return self.pending
    def pending_put(self, _key, _subject, value):
        self.pending = value
    def pending_delete(self, _key, _subject):
        self.pending = None
    def list_admin(self):
        return records
    def admin_disable(self, _authority, automation_id, _reason):
        self.disabled = automation_id
        return next(row for row in records if row["automation_id"] == automation_id)

class Service:
    def __init__(self):
        self.store = Store()

class Authority:
    subject = owner

service = Service()
route = namespace["_hades_phase3_owner_response"]
inventory = route("What automations do I have?", Authority(), service, "pending")
assert "draft automations" in inventory.lower() and "none are running" in inventory.lower()
assert inventory.count("Low Inventory Summary") == 2
assert "for you" in inventory and "for a household member" in inventory, inventory
assert "Groceries" in inventory and "grocy.household" not in inventory
assert "synthetic-" not in inventory and "private-record-id" not in inventory
distinct_owners = route("Are any duplicate automations?", Authority(), service, "pending")
assert "none found" in distinct_owners and "synthetic-" not in distinct_owners

duplicate = route("disable my low inventory summary", Authority(), service, "pending")
assert "Shall I disable it?" in duplicate and "for you" in duplicate
assert "synthetic-" not in duplicate and "private-record-id" not in duplicate
disabled = route("yes", Authority(), service, "pending")
assert "Disabled Low Inventory Summary for you" in disabled
assert "synthetic-" not in disabled and "private-record-id" not in disabled
assert service.store.disabled == "private-record-id-1"
records.append({**records[0], "automation_id": "private-record-id-3"})
same_owner = route("Are any duplicate automations?", Authority(), service, "pending")
assert "Low Inventory Summary (2 for you)" in same_owner
assert "synthetic-" not in same_owner and "private-record-id" not in same_owner

actor = Phase3Authority(other, "household", frozenset({"grocy.household"}))
runtime_service = Phase3Service(
    Phase3Store(tempfile.mktemp(prefix="hades-phase3-surface-")),
    catalog=Phase3Catalog(),
)
preview = runtime_service.preview(actor, "low-inventory-summary", {})
record = runtime_service.confirm(actor, preview["preview_id"], preview["preview_hash"], "synthetic-create")
namespace["_hades_phase3_enabled"] = lambda: True
namespace["_hades_phase3_authority"] = lambda _subject, _scope: actor
namespace["_hades_phase3_service"] = lambda: runtime_service
phase3_route = namespace["_hades_phase3_response"]

# A bare confirmation in another Open WebUI chat must not consume the only
# pending action for this household identity.
runtime_service.store.pending_put(
    f"session:{other}:chat-alpha",
    other,
    {"kind": "action", "action": "pause", "automation_id": record["automation_id"]},
)
cross_chat_confirmation = phase3_route("yes", other, "household", "chat-beta")
assert "couldn't match that confirmation" in cross_chat_confirmation.lower()
assert runtime_service.store.get(record["automation_id"])["enabled"] is True
assert not any(row["action"] == "pause" for row in runtime_service.store.audit_for(record["automation_id"]))
same_chat_confirmation = phase3_route("yes", other, "household", "chat-alpha")
assert "paused" in same_chat_confirmation.lower()
assert runtime_service.store.get(record["automation_id"])["enabled"] is False

listed = phase3_route("What automations do I have?", other, "household")
assert "not running" in listed.lower() and "Low Inventory Summary" in listed
assert "low-inventory-summary" not in listed and "synthetic-" not in listed
run = phase3_route("run my low inventory summary", other, "household", "chat-alpha")
assert "not connected to the HADES runner" in run and "have not run it" in run
assert runtime_service.store.get(record["automation_id"])["manual_runs"] == 0
assert not any(row["action"] == "run" for row in runtime_service.store.audit_for(record["automation_id"]))
missing_chat_control = phase3_route("resume my low inventory summary", other, "household")
assert "couldn't securely tie" in missing_chat_control.lower()
assert runtime_service.store.get(record["automation_id"])["enabled"] is False
resume_preview = phase3_route("resume my low inventory summary", other, "household", "chat-alpha")
assert "Shall I resume" in resume_preview
resumed = phase3_route("yes", other, "household", "chat-alpha")
assert "still will not run on a schedule" in resumed
assert runtime_service.store.get(record["automation_id"])["enabled"] is True
for suffix in ("", "-wal", "-shm"):
    Path(str(runtime_service.store.path) + suffix).unlink(missing_ok=True)
print("PASS Phase 3 owner/household surfaces hide IDs, explain draft state, and never claim a staged run executed")
PY
