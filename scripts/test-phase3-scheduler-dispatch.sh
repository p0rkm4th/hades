#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
import sqlite3
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from integrations.automation.phase3_request import sign_due_request, sign_request
from integrations.automation.phase3_request import make_phase3_http_handler
from integrations.automation.phase3_self_service import (
    Phase3Authority, Phase3Catalog, Phase3Runner, Phase3Service, Phase3Store,
)

secret = b"synthetic-scheduler-run-key-at-least-32-bytes"
owner = Phase3Authority("synthetic-owner", "owner", frozenset({"grocy.household", "hades-core.health", "rollback-probe.health"}))
with tempfile.TemporaryDirectory(prefix="hades-phase3-scheduler-") as tmp:
    path = tmp + "/phase3.sqlite"
    store = Phase3Store(path)
    service = Phase3Service(store, Phase3Catalog({"hades-core": "HADES Core", "rollback-probe": "Rollback probe"}))
    created = {}
    for template, payload in (
        ("low-inventory-summary", {"interval_minutes": 5}),
        ("server-health-watch", {"resource_id": "hades-core", "display_name": "Core", "interval_minutes": 5}),
    ):
        preview = service.preview(owner, template, payload)
        created[template] = service.confirm(
            owner, preview["preview_id"], preview["preview_hash"], "scheduler-" + template,
        )
    now = int(time.time())
    with sqlite3.connect(path) as db:
        db.execute("UPDATE phase3_automations SET updated_at=?", (now - 1200,))

    calls = []
    runner = Phase3Runner(
        store, lambda subject: owner if subject == owner.subject else Phase3Authority(subject, "household", frozenset()),
        {
            "low-inventory-summary": lambda _payload: calls.append("inventory") or {"hades_state": "READY"},
            "server-health-watch": lambda _payload: calls.append("health") or {"hades_state": "UP"},
        },
    )
    runner_factory_calls = []
    handler = make_phase3_http_handler(
        lambda: secret, lambda: runner_factory_calls.append(True) or runner,
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        def poll_due(template):
            body = json.dumps({"template_type": template}, separators=(",", ":")).encode()
            timestamp = str(int(time.time()))
            headers = {
                "Content-Type": "application/json",
                "X-HADES-Timestamp": timestamp,
                "X-HADES-Signature": sign_due_request(secret, timestamp, body),
            }
            request = Request(
                f"http://127.0.0.1:{server.server_port}/v1/epsilon/phase3/due",
                data=body, headers=headers, method="POST",
            )
            with urlopen(request, timeout=3) as response:
                return json.loads(response.read())["due"]

        timestamp = str(int(time.time()))
        due = (
            poll_due("low-inventory-summary")
            + poll_due("server-health-watch")
        )
        assert len(due) == 2 and all(set(row) == {"automation_id", "execution_key", "due_at"} for row in due)
        assert all(row["execution_key"] == f"schedule:{row['due_at']}" for row in due)

        for row in due:
            # Dispatch accepts only the two fields in the fixed run contract;
            # due_at is scheduling metadata, not forwarded to /run.
            run_body = json.dumps({
                "automation_id": row["automation_id"],
                "execution_key": row["execution_key"],
            }, separators=(",", ":")).encode()
            run_headers = {
                "Content-Type": "application/json",
                "X-HADES-Timestamp": timestamp,
                "X-HADES-Signature": sign_request(secret, timestamp, run_body),
            }
            request = Request(
                f"http://127.0.0.1:{server.server_port}/v1/epsilon/phase3/run",
                data=run_body, headers=run_headers, method="POST",
            )
            with urlopen(request, timeout=3) as response:
                assert json.loads(response.read())["status"] == "COMPLETE"
            with urlopen(request, timeout=3) as response:
                replay = json.loads(response.read())
            assert replay["replayed"] is True
        assert len(calls) == 2, calls
        assert poll_due("low-inventory-summary") == []
        assert poll_due("server-health-watch") == []

        # Rollback after a scheduler has already observed a due item must
        # invalidate that stale dispatch. Pausing removes it from future due
        # batches and the signed run route must fail closed before a source read.
        rollback_preview = service.preview(owner, "server-health-watch", {
            "resource_id": "rollback-probe", "display_name": "Rollback probe", "interval_minutes": 5,
        })
        rollback_item = service.confirm(
            owner, rollback_preview["preview_id"], rollback_preview["preview_hash"], "scheduler-rollback",
        )
        with sqlite3.connect(path) as db:
            db.execute(
                "UPDATE phase3_automations SET updated_at=? WHERE automation_id=?",
                (now - 1200, rollback_item["automation_id"]),
            )
        stale_dispatch = next(
            row for row in poll_due("server-health-watch")
            if row["automation_id"] == rollback_item["automation_id"]
        )
        paused = service.control(owner, rollback_item["automation_id"], "pause")
        assert paused["enabled"] is False
        assert not any(
            row["automation_id"] == rollback_item["automation_id"]
            for row in poll_due("server-health-watch")
        )
        stale_body = json.dumps({
            "automation_id": stale_dispatch["automation_id"],
            "execution_key": stale_dispatch["execution_key"],
        }, separators=(",", ":")).encode()
        stale_timestamp = str(int(time.time()))
        stale_request = Request(
            f"http://127.0.0.1:{server.server_port}/v1/epsilon/phase3/run",
            data=stale_body,
            headers={
                "Content-Type": "application/json",
                "X-HADES-Timestamp": stale_timestamp,
                "X-HADES-Signature": sign_request(secret, stale_timestamp, stale_body),
            },
            method="POST",
        )
        try:
            urlopen(stale_request, timeout=3)
        except HTTPError as exc:
            assert exc.code == 403
        else:
            raise AssertionError("stale due dispatch ran after schedule rollback")
        assert len(calls) == 2, "paused stale dispatch reached an approved source"
        assert service.store.get(rollback_item["automation_id"])["enabled"] is False
        assert any(row["action"] == "pause" for row in service.store.audit_for(rollback_item["automation_id"]))

        # An expired lease becomes UNKNOWN and must not be selected for a new
        # automatic run, even when a later interval is due.
        preview = service.preview(owner, "weekly-household-summary", {
            "interval_minutes": 5, "resource_scope": ["grocy.household"],
        })
        weekly = service.confirm(owner, preview["preview_id"], preview["preview_hash"], "scheduler-unknown")
        base = now - 1200
        with sqlite3.connect(path) as db:
            db.execute("UPDATE phase3_automations SET updated_at=? WHERE automation_id=?", (base, weekly["automation_id"]))
        due_at = base + ((now - base) // 300) * 300
        unknown_key = f"schedule:{due_at}"
        store.claim_run(weekly["automation_id"], unknown_key, owner)
        with sqlite3.connect(path) as db:
            db.execute(
                "UPDATE phase3_runs SET started_at=? WHERE automation_id=? AND execution_key=?",
                (now - 121, weekly["automation_id"], unknown_key),
            )
        unknown = runner.run(weekly["automation_id"], unknown_key)
        assert unknown["status"] == "UNKNOWN" and "weekly" not in calls
        assert not any(row["automation_id"] == weekly["automation_id"] for row in store.due_schedule_items(now=now))
        try:
            store.due_schedule_items(now=now, limit=26)
        except ValueError:
            pass
        else:
            raise AssertionError("due selector accepted an out-of-range batch limit")

        factory_count = len(runner_factory_calls)
        body = b"{}"
        headers = {
            "Content-Type": "application/json",
            "X-HADES-Timestamp": timestamp,
            "X-HADES-Signature": sign_due_request(secret, timestamp, body),
        }
        bad = Request(
            f"http://127.0.0.1:{server.server_port}/v1/epsilon/phase3/due",
            data=body, headers={**headers, "X-HADES-Signature": "0" * 64}, method="POST",
        )
        try:
            urlopen(bad, timeout=3)
        except HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("due selector accepted an invalid signature")
        assert len(runner_factory_calls) == factory_count, "invalid due poll opened runner state"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

print("PASS Phase 3 due dispatch and rollback: signed fixed route, bounded due records, stable slot keys, one-read replay, stale dispatch denied after pause")
PY
