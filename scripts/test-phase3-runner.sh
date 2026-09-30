#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from integrations.automation.phase3_self_service import (
    Phase3Authority,
    Phase3AuthorizationError,
    Phase3Catalog,
    Phase3Runner,
    Phase3Service,
    Phase3Store,
)

OWNER = Phase3Authority("owner-subject", "owner", frozenset({
    "hades-core.health", "grocy.household", "backup.evidence",
}))


def create(path, template="low-inventory-summary"):
    store = Phase3Store(str(path))
    service = Phase3Service(store, Phase3Catalog({"hades-core": "HADES Core"}))
    payload = {"resource_id": "hades-core"} if template == "server-health-watch" else {}
    preview = service.preview(OWNER, template, payload)
    item = service.confirm(OWNER, preview["preview_id"], preview["preview_hash"], "fixture:" + template)
    return store, item


with tempfile.TemporaryDirectory(prefix="hades-phase3-runner-") as tmp:
    root = Path(tmp)
    private_state_dir = root / "private-state"
    private_store = Phase3Store(str(private_state_dir / "runs.sqlite"))
    assert private_state_dir.stat().st_mode & 0o777 == 0o700
    assert private_store.path.stat().st_mode & 0o777 == 0o600

    # Moving Phase 3 to its isolated database preserves its existing records
    # and leaves unrelated shared-state tables behind.
    legacy, legacy_item = create(root / "legacy-shared.sqlite")
    with __import__("sqlite3").connect(legacy.path) as db:
        db.execute("CREATE TABLE unrelated_fixture(value TEXT)")
        db.execute("INSERT INTO unrelated_fixture VALUES('must stay in legacy DB')")
    isolated = Phase3Store(str(root / "isolated-phase3.sqlite"))
    copied = isolated.import_legacy_database(str(legacy.path))
    assert copied >= 2, (copied, legacy.list_admin())
    assert isolated.get(legacy_item["automation_id"])["owner_subject_id"] == OWNER.subject
    assert isolated.import_legacy_database(str(legacy.path)) == 0
    with __import__("sqlite3").connect(isolated.path) as db:
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='unrelated_fixture'").fetchone()
    with __import__("sqlite3").connect(legacy.path) as db:
        assert db.execute("SELECT value FROM unrelated_fixture").fetchone()[0] == "must stay in legacy DB"

    # Successful run is idempotent and result reads require current owner grants.
    store, item = create(root / "success.sqlite")
    authorities = {OWNER.subject: OWNER}
    calls = []
    runner = Phase3Runner(
        store,
        authorities.__getitem__,
        {"low-inventory-summary": lambda payload: calls.append(dict(payload)) or {"state": "READY", "low": ["milk"]}},
    )
    first = runner.run(item["automation_id"], "n8n-exec-100")
    replay = runner.run(item["automation_id"], "n8n-exec-100")
    assert first["status"] == "COMPLETE" and first["result"] == {"state": "READY", "low": ["milk"]}
    assert replay["status"] == "COMPLETE" and replay["replayed"] is True and len(calls) == 1
    result = runner.result_for(first["run_id"], OWNER)
    assert result["result"]["low"] == ["milk"]
    stranger = Phase3Authority("stranger", "household", frozenset({"grocy.household"}))
    try:
        runner.result_for(first["run_id"], stranger)
    except Phase3AuthorizationError:
        pass
    else:
        raise AssertionError("unshared actor received a protected run result")
    recipient = Phase3Authority("recipient", "household", frozenset({"grocy.household"}))
    store.share(OWNER, item["automation_id"], recipient)
    assert runner.result_for(first["run_id"], recipient)["result"]["state"] == "READY"
    store.share(OWNER, item["automation_id"], recipient, revoke=True)
    try:
        runner.result_for(first["run_id"], recipient)
    except Phase3AuthorizationError:
        pass
    else:
        raise AssertionError("revoked recipient retained a protected run result")
    authorities[OWNER.subject] = Phase3Authority(OWNER.subject, "owner", frozenset())
    try:
        runner.run(item["automation_id"], "n8n-exec-100")
    except Phase3AuthorizationError:
        pass
    else:
        raise AssertionError("duplicate delivery returned a result after owner grant revocation")
    try:
        runner.result_for(first["run_id"], OWNER)
    except Phase3AuthorizationError:
        pass
    else:
        raise AssertionError("owner resource revocation retained a protected run result")

    # A current failure still reports the most recent successful evidence per
    # repository target without letting a bad result overwrite last-good time.
    backup_store, backup_item = create(root / "backup-last-good.sqlite", "hades-backup-verification")
    backup_authorities = {OWNER.subject: OWNER}
    backup_results = [
        {"hades_state": "HEALTHY", "targets": [
            {"target": "hades", "hades_state": "HEALTHY", "artifact_mtime": 1790209800.0, "observed_at": 1790270000.0},
            {"target": "infra", "hades_state": "HEALTHY", "artifact_mtime": 1790209900.0, "observed_at": 1790270000.0},
        ]},
        {"hades_state": "ATTENTION", "targets": [
            {"target": "hades", "hades_state": "STALE", "artifact_mtime": 1790209800.0, "observed_at": 1790356400.0},
            {"target": "infra", "hades_state": "MISSING", "observed_at": 1790356400.0},
        ]},
    ]
    backup_runner = Phase3Runner(
        backup_store, backup_authorities.__getitem__,
        {"hades-backup-verification": lambda _payload: backup_results.pop(0)},
    )
    backup_runner.run(backup_item["automation_id"], "backup-success")
    latest_backup = backup_runner.run(backup_item["automation_id"], "backup-failure")
    rendered_backup = backup_runner.recent_results_for(OWNER.subject)[0]["result"]
    assert latest_backup["result"]["hades_state"] == "ATTENTION"
    assert rendered_backup["targets"][0]["hades_state"] == "STALE"
    assert rendered_backup["last_success_by_target"]["hades"]["artifact_mtime"] == 1790209800.0
    assert rendered_backup["last_success_by_target"]["infra"]["artifact_mtime"] == 1790209900.0
    assert set(rendered_backup["last_success_by_target"]) == {"hades", "infra"}

    # A fresh authority check after reservation catches grant revocation before
    # dispatching the canonical reader.
    store, item = create(root / "revoked-before-read.sqlite", "server-health-watch")
    reads = []

    runner = Phase3Runner(store, lambda _subject: OWNER, {
        "server-health-watch": lambda payload: reads.append(dict(payload)) or {"state": "UP"},
    }, catalog=Phase3Catalog({"hades-core": "HADES Core"}))
    # The callback switches to a revoked authority on its second lookup.
    lookup_count = {"value": 0}

    def revoke_after_reservation(subject):
        lookup_count["value"] += 1
        return OWNER if lookup_count["value"] == 1 else Phase3Authority(subject, "owner", frozenset())

    runner.authority_for_subject = revoke_after_reservation
    refused = runner.run(item["automation_id"], "n8n-exec-revoked")
    assert refused["status"] == "FAILED" and not reads, refused

    # A failed authority lookup before reservation leaves no run record; a
    # lookup failure after reservation closes the row as FAILED without a read.
    store, item = create(root / "authority-unavailable-before-claim.sqlite", "server-health-watch")
    reads = []

    def authority_unavailable(_subject):
        raise OSError("synthetic authority service detail")

    runner = Phase3Runner(store, authority_unavailable, {
        "server-health-watch": lambda payload: reads.append(dict(payload)) or {"state": "UP"},
    }, catalog=Phase3Catalog({"hades-core": "HADES Core"}))
    try:
        runner.run(item["automation_id"], "n8n-authority-unavailable-before")
    except Phase3AuthorizationError as exc:
        assert "synthetic authority service detail" not in str(exc)
    else:
        raise AssertionError("unavailable current-authority source did not fail closed")
    with __import__("sqlite3").connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM phase3_runs").fetchone()[0] == 0
    assert not reads

    store, item = create(root / "authority-unavailable-after-claim.sqlite", "server-health-watch")
    reads = []
    lookups = {"count": 0}

    def authority_fails_before_dispatch(subject):
        lookups["count"] += 1
        if lookups["count"] == 1:
            return OWNER
        raise OSError("synthetic authority service detail")

    runner = Phase3Runner(store, authority_fails_before_dispatch, {
        "server-health-watch": lambda payload: reads.append(dict(payload)) or {"state": "UP"},
    }, catalog=Phase3Catalog({"hades-core": "HADES Core"}))
    unavailable = runner.run(item["automation_id"], "n8n-authority-unavailable-after")
    assert unavailable["status"] == "FAILED" and not reads, unavailable
    assert "synthetic authority service detail" not in unavailable["reason"]
    assert store.get_run(unavailable["run_id"])["status"] == "FAILED"

    # Concurrent duplicate deliveries reserve one run and dispatch one read.
    store, item = create(root / "concurrent.sqlite")
    entered = threading.Event()
    release = threading.Event()
    concurrent_reads = []

    def slow_read(payload):
        concurrent_reads.append(dict(payload))
        entered.set()
        release.wait(timeout=5)
        return {"state": "READY"}

    runner = Phase3Runner(store, lambda _subject: OWNER, {"low-inventory-summary": slow_read})
    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(runner.run, item["automation_id"], "n8n-exec-race")
        assert entered.wait(timeout=2)
        duplicate = runner.run(item["automation_id"], "n8n-exec-race")
        release.set()
        first = first_future.result(timeout=5)
    assert len(concurrent_reads) == 1
    assert duplicate["status"] == "RUNNING" and first["status"] == "COMPLETE"

    # A crashed runner's expired lease becomes UNKNOWN; the same delivery is
    # never replayed automatically.
    store, item = create(root / "unknown.sqlite")
    claim = store.claim_run(item["automation_id"], "n8n-exec-lost", OWNER)
    with __import__("sqlite3").connect(store.path) as db:
        db.execute("UPDATE phase3_runs SET started_at=started_at-300 WHERE run_id=?", (claim["run"]["run_id"],))
    lost_reads = []
    runner = Phase3Runner(store, lambda _subject: OWNER, {
        "low-inventory-summary": lambda payload: lost_reads.append(dict(payload)) or {"state": "READY"},
    })
    unknown = runner.run(item["automation_id"], "n8n-exec-lost")
    assert unknown["status"] == "UNKNOWN" and not lost_reads

    # A known source failure is recorded without leaking the provider message.
    store, item = create(root / "failed.sqlite")
    runner = Phase3Runner(store, lambda _subject: OWNER, {
        "low-inventory-summary": lambda _payload: (_ for _ in ()).throw(RuntimeError("private source detail")),
    })
    failed = runner.run(item["automation_id"], "n8n-exec-failed")
    assert failed["status"] == "FAILED" and "private source detail" not in failed["reason"]

print("PASS Phase 3 fixed-source runner: authority outage/revocation, one-read idempotency, unknown outcomes, failure redaction, and result isolation")
PY
