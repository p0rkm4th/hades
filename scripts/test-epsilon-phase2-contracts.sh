#!/usr/bin/env bash
set -Eeuo pipefail
python3 - <<'PY'
import hashlib, tempfile, time
from pathlib import Path
from integrations.automation import InventorySummaryService, LifecycleStore, SummaryHistory, TypedLifecycle, UnknownMutation, build_inventory_n8n_workflow, build_weekly_n8n_workflow, compose_summary, notification_transition, render_summary, summarize_grocy
from integrations.automation.inventory_summary import InventoryObservation
from integrations.automation.backup_verification import BackupTarget, BackupVerificationService, BackupVerificationSpec, verify_target

with tempfile.TemporaryDirectory() as root:
    p = Path(root) / "bundle"
    p.write_bytes(b"valid evidence")
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    target = BackupTarget("x", "x", p, digest, "test", 3600)
    assert verify_target(target, now=time.time()).state == "HEALTHY"
    assert verify_target(BackupTarget("x", "x", Path(root)/"missing", digest, "test", 3600), now=time.time()).state == "MISSING"
    assert verify_target(BackupTarget("x", "x", p, "0" * 64, "test", 3600), now=time.time()).state == "FAILED"
    assert notification_transition("HEALTHY", "STALE")
    assert not notification_transition("FAILED", "FAILED")
    service = BackupVerificationService(str(Path(root) / "state.sqlite"), BackupVerificationSpec("backup", "owner"))
    healthy = service.observe([verify_target(target, now=time.time())])
    assert healthy["state"] == "HEALTHY" and not healthy["notify"]
    failed = service.observe([verify_target(BackupTarget("x", "x", p, "0" * 64, "test", 3600), now=time.time())])
    assert failed["state"] == "FAILED" and failed["notify"]
    repeated = service.observe([verify_target(BackupTarget("x", "x", p, "0" * 64, "test", 3600), now=time.time())])
    assert repeated["state"] == "FAILED" and not repeated["notify"]

inventory = summarize_grocy([
    {"product": {"name": "Milk"}, "amount_aggregated": 1, "amount_aggregated_min_stock": 2},
    {"product": {"name": "Bread"}, "amount_aggregated": 0, "amount_aggregated_min_stock": 1},
])
assert inventory.low == ("Milk",) and inventory.out == ("Bread",)
assert "Out of stock: Bread." in render_summary(inventory)
assert "no stock conclusion" in render_summary(type("Unavailable", (), {"state":"SOURCE_UNAVAILABLE"})())
with tempfile.TemporaryDirectory() as root:
    service = InventorySummaryService(str(Path(root) / "inventory.sqlite"), "groceries", "owner")
    assert service.record(inventory, render_summary(inventory), "now")["notify"]
    assert not service.record(inventory, render_summary(inventory), "later")["notify"]

summary = compose_summary({"grocy": ("Groceries", lambda: "Milk is low."), "backup": ("Backups", lambda: "")}, lambda key: key != "backup")
assert "Groceries:" in summary and "Milk is low." in summary and "Backups:" not in summary
def unavailable_source():
    raise RuntimeError("synthetic source outage")
partial = compose_summary({"grocy": ("Groceries", unavailable_source), "backup": ("Backups", lambda: "healthy"), "health": ("Servers", lambda: "up")}, lambda key: True)
assert "Backups:" in partial and "Servers:" in partial and "Unavailable this week: Groceries." in partial
assert "no stock conclusion" in render_summary(InventoryObservation("SOURCE_UNAVAILABLE", reason="fixture source outage"))
with tempfile.TemporaryDirectory() as root:
    failure_store = BackupVerificationService(str(Path(root) / "failure.sqlite"), BackupVerificationSpec("failure-fixture", "owner"))
    for state in ("SOURCE_UNAVAILABLE", "FAILED", "MISSING", "STALE", "UNKNOWN", "HEALTHY"):
        observed = failure_store.reconcile_execution({"hades_state": state, "hades_reason": "typed fixture", "observed_at": "fixture"})
        assert observed["state"] == state
    assert failure_store.status()["state"] == "HEALTHY"
with tempfile.TemporaryDirectory() as root:
    history = SummaryHistory(str(Path(root) / "history.sqlite"), limit=2)
    history.record("household-a", "one", "first")
    history.record("household-a", "two", "second", "Backups")
    assert history.latest("household-a")["text"] == "second"
with tempfile.TemporaryDirectory() as root:
    lifecycle = TypedLifecycle(LifecycleStore(str(Path(root) / "lifecycle.sqlite")))
    preview = lifecycle.preview("owner", "hades-backup-verification", {"schedule": "daily"})
    staged = lifecycle.confirm("owner", preview, confirmed=True, operation_key="create-1")
    assert staged["status"] == "STAGED" and staged["production_schedule"] is False
    assert lifecycle.confirm("owner", preview, confirmed=True, operation_key="create-1") == staged
    assert lifecycle.mutate("owner", "hades-backup-verification", "edit", {"schedule": "daily"}, confirmed=True, operation_key="edit-1")["status"] == "STAGED"
    try:
        lifecycle.confirm("household-a", preview, confirmed=True, operation_key="create-2")
    except Exception:
        pass
    else:
        raise AssertionError("non-owner confirmation escaped staged lifecycle")
graph = build_inventory_n8n_workflow("staged-inventory", 7)
assert graph["active"] is False and all(node["type"] != "n8n-nodes-base.code" for node in graph["nodes"])
weekly = build_weekly_n8n_workflow("staged-weekly")
assert any(node["name"] == "Bounded server health result projection" for node in weekly["nodes"])
assert weekly["connections"]["Authorized server health result source"]["main"][0][0]["node"] == "Bounded server health result projection"
assert weekly["active"] is False
weekly_nodes = {node["name"]: node for node in weekly["nodes"]}
for source_name in (
    "Authorized Grocy result source",
    "Authorized backup result source",
    "Authorized server health result source",
):
    source = weekly_nodes[source_name]
    assert source["onError"] == "continueRegularOutput", source_name
    assert source["parameters"]["response"]["response"]["neverError"] is True, source_name
merge = weekly_nodes["Bounded source result collection"]
assert merge["parameters"]["mode"] == "append" and merge["parameters"]["numberInputs"] == 3
connections = weekly["connections"]
assert connections["Authorized Grocy result source"]["main"][0][0] == {
    "node": "Bounded source result collection", "type": "main", "index": 0,
}
assert connections["Authorized backup result source"]["main"][0][0] == {
    "node": "Bounded source result collection", "type": "main", "index": 1,
}
assert connections["Bounded server health result projection"]["main"][0][0] == {
    "node": "Bounded source result collection", "type": "main", "index": 2,
}
print("PASS Epsilon Phase 2 typed contracts")
PY
for required in config/epsilon-workflows/backup-verification.json config/epsilon-workflows/low-inventory-summary.json config/epsilon-backup-evidence.json; do
  test -s "$required"
done
python3 - <<'PY'
from integrations.automation import BACKUP_TARGETS, build_backup_n8n_workflow
for target in BACKUP_TARGETS:
    graph = build_backup_n8n_workflow("staged-" + target, target, 1440)
    assert graph["active"] is False
    assert all(node["type"] != "n8n-nodes-base.executeCommand" for node in graph["nodes"])
print("PASS fixed backup n8n graph has only allowlisted source targets")
PY
python3 - <<'PY'
import importlib.util
from pathlib import Path

path = Path("integrations/epsilon-source/server.py")
spec = importlib.util.spec_from_file_location("hades_epsilon_source_fixture", path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
module.verify = lambda target: {
    "hades_template": "backup-verification", "target": target,
    "hades_state": "HEALTHY", "observed_at": 1790270000,
    "artifact_mtime": 1790209800,
}
result = module._phase3_backup_read({})
assert result["hades_state"] == "HEALTHY"
assert [item["target"] for item in result["targets"]] == ["hades", "infra"]
assert all("observed_at" in item and "artifact_mtime" in item for item in result["targets"])
print("PASS canonical backup source preserves per-repository state and artifact/check timestamps")
PY
echo 'PASS Epsilon Phase 2 fixed template artifacts'
