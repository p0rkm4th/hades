#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
import sqlite3
import threading
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from integrations.automation.phase3_request import (
    Phase3RequestError,
    execute_signed_run,
    sign_results_request,
    make_phase3_http_handler,
    parse_run_request,
    sign_request,
)
from integrations.automation.phase3_self_service import (
    Phase3Authority,
    Phase3Catalog,
    Phase3Runner,
    Phase3Service,
    Phase3Store,
)

secret = b"synthetic-test-key-material-at-least-32-bytes"
result_secret = b"synthetic-hades-result-key-material-at-least-32-bytes"
now = 1_800_000_000
timestamp = str(now)
with tempfile.TemporaryDirectory(prefix="hades-phase3-request-") as tmp:
    owner = Phase3Authority("owner-subject", "owner", frozenset({"grocy.household"}))
    store = Phase3Store(tmp + "/phase3.sqlite")
    service = Phase3Service(store, Phase3Catalog())
    preview = service.preview(owner, "low-inventory-summary", {})
    item = service.confirm(owner, preview["preview_id"], preview["preview_hash"], "request-fixture")
    calls = []
    runner = Phase3Runner(
        store,
        lambda subject: owner if subject == owner.subject else Phase3Authority(subject, "household", frozenset()),
        {"low-inventory-summary": lambda _payload: calls.append("read") or {"state": "READY"}},
    )
    body = json.dumps({"automation_id": item["automation_id"], "execution_key": "n8n-exec-42"}, separators=(",", ":")).encode()
    signature = sign_request(secret, timestamp, body)
    first = execute_signed_run(secret=secret, timestamp=timestamp, signature=signature, raw_body=body, runner=runner, now=now)
    replay = execute_signed_run(secret=secret, timestamp=timestamp, signature=signature, raw_body=body, runner=runner, now=now)
    assert first["status"] == "COMPLETE" and replay["replayed"] is True and calls == ["read"]

    def rejects(**kwargs):
        try:
            execute_signed_run(runner=runner, now=now, **kwargs)
        except Phase3RequestError:
            return
        raise AssertionError("invalid runner request was accepted")

    rejects(secret=secret, timestamp=timestamp, signature="0" * 64, raw_body=body)
    rejects(secret=secret, timestamp=str(now - 121), signature=sign_request(secret, str(now - 121), body), raw_body=body)
    rejects(secret=secret, timestamp=timestamp, signature=signature, raw_body=body + b" ")
    for invalid in (
        b'{"automation_id":"' + item["automation_id"].encode() + b'","execution_key":"x","extra":true}',
        b'{"automation_id":"' + item["automation_id"].encode() + b'","automation_id":"' + item["automation_id"].encode() + b'","execution_key":"x"}',
        b'{"automation_id":"arbitrary","execution_key":"x"}',
    ):
        rejects(secret=secret, timestamp=timestamp, signature=sign_request(secret, timestamp, invalid), raw_body=invalid)

    try:
        parse_run_request(b"x" * 2049)
    except Phase3RequestError:
        pass
    else:
        raise AssertionError("oversized request was accepted")

    http_store = Phase3Store(tmp + "/http-phase3.sqlite")
    http_service = Phase3Service(http_store, Phase3Catalog())
    preview = http_service.preview(owner, "low-inventory-summary", {})
    http_item = http_service.confirm(owner, preview["preview_id"], preview["preview_hash"], "http-fixture")
    recipient = Phase3Authority("recipient-subject", "household", frozenset({"grocy.household"}))
    http_store.share(owner, http_item["automation_id"], recipient)
    authorities = {owner.subject: owner, recipient.subject: recipient}
    http_runner = Phase3Runner(
        http_store,
        lambda subject: authorities.get(subject, Phase3Authority(subject, "household", frozenset(), False)),
        {"low-inventory-summary": lambda _payload: calls.append("http-read") or {"state": "READY"}},
    )
    runner_factory_calls = []
    handler = make_phase3_http_handler(
        lambda: secret, lambda: runner_factory_calls.append(True) or http_runner,
        lambda: result_secret,
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        http_body = json.dumps({"automation_id": http_item["automation_id"], "execution_key": "n8n-http-42"}, separators=(",", ":")).encode()
        http_timestamp = str(int(__import__("time").time()))
        http_signature = sign_request(secret, http_timestamp, http_body)
        request = Request(
            f"http://127.0.0.1:{server.server_port}/v1/epsilon/phase3/run",
            data=http_body,
            headers={"Content-Type": "application/json", "X-HADES-Timestamp": http_timestamp, "X-HADES-Signature": http_signature},
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            first_http = json.loads(response.read())
        with urlopen(request, timeout=3) as response:
            replay_http = json.loads(response.read())
        assert first_http["status"] == "COMPLETE" and replay_http["replayed"] is True
        assert calls.count("http-read") == 1 and len(runner_factory_calls) == 2

        result_body = json.dumps({
            "requester_subject_id": recipient.subject,
        }, separators=(",", ":")).encode()
        result_timestamp = str(int(__import__("time").time()))
        result_headers = {
            "Content-Type": "application/json",
            "X-HADES-Timestamp": result_timestamp,
            "X-HADES-Signature": sign_results_request(result_secret, result_timestamp, result_body),
        }
        result_request = Request(
            f"http://127.0.0.1:{server.server_port}/v1/epsilon/phase3/results",
            data=result_body, headers=result_headers, method="POST",
        )
        with urlopen(result_request, timeout=3) as response:
            shared_result = json.loads(response.read())
        assert len(shared_result["results"]) == 1
        assert shared_result["results"][0]["result"]["state"] == "READY"
        assert shared_result["results"][0]["template_type"] == "low-inventory-summary"
        assert "run_id" not in shared_result["results"][0]
        assert len(runner_factory_calls) == 3

        # The n8n run key cannot authenticate as the HADES result-query key.
        wrong_result_key = Request(
            f"http://127.0.0.1:{server.server_port}/v1/epsilon/phase3/results",
            data=result_body,
            headers={**result_headers, "X-HADES-Signature": sign_request(secret, result_timestamp, result_body)},
            method="POST",
        )
        try:
            urlopen(wrong_result_key, timeout=3)
        except HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("n8n run key authenticated a result query")
        assert len(runner_factory_calls) == 3, "invalid result signature opened runner state"

        authorities[recipient.subject] = Phase3Authority(
            recipient.subject, "household", frozenset(), False,
        )
        try:
            urlopen(result_request, timeout=3)
        except HTTPError as exc:
            assert exc.code == 403 and b"private" not in exc.read().lower()
        else:
            raise AssertionError("revoked requester retained access to a shared result")
        assert len(runner_factory_calls) == 4

        bad = Request(
            f"http://127.0.0.1:{server.server_port}/v1/epsilon/phase3/run",
            data=http_body,
            headers={"Content-Type": "application/json", "X-HADES-Timestamp": http_timestamp, "X-HADES-Signature": "0" * 64},
            method="POST",
        )
        try:
            urlopen(bad, timeout=3)
        except HTTPError as exc:
            assert exc.code == 401 and b"private" not in exc.read().lower()
        else:
            raise AssertionError("HTTP handler accepted an invalid signature")
        assert len(runner_factory_calls) == 4, "invalid signature opened runner state"

        wrong_path = Request(
            f"http://127.0.0.1:{server.server_port}/v1/epsilon/phase3/other",
            data=http_body, method="POST",
        )
        try:
            urlopen(wrong_path, timeout=3)
        except HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("HTTP handler accepted an unregistered route")

        # Bounded load matches the owner quota: admit and dispatch the maximum
        # ten active schedules concurrently through the real signed HTTP
        # handler. One fixed reader fails to exercise HTTP failure redaction
        # and safe idempotent retry alongside successful schedules.
        load_resources = {f"synthetic-core-{n}": f"Synthetic Core {n}" for n in range(10)}
        load_grants = frozenset(f"{resource}.health" for resource in load_resources)
        load_owner = Phase3Authority("load-owner", "owner", load_grants)
        load_store = Phase3Store(tmp + "/load-phase3.sqlite")
        load_service = Phase3Service(load_store, Phase3Catalog(load_resources))
        load_items = []
        for resource in load_resources:
            preview = load_service.preview(load_owner, "server-health-watch", {
                "resource_id": resource, "interval_minutes": 5,
            })
            load_items.append(load_service.confirm(
                load_owner, preview["preview_id"], preview["preview_hash"], "load:" + resource,
            ))

        load_reads = Counter()
        load_reads_lock = threading.Lock()

        def load_reader(payload):
            resource = payload["resource_id"]
            with load_reads_lock:
                load_reads[resource] += 1
            time.sleep(0.02)
            if resource == "synthetic-core-9":
                raise RuntimeError("synthetic private source detail")
            return {"state": "UP", "resource_id": resource}

        load_runner = Phase3Runner(
            load_store, lambda subject: load_owner if subject == load_owner.subject else
            Phase3Authority(subject, "household", frozenset(), False),
            {"server-health-watch": load_reader}, catalog=Phase3Catalog(load_resources),
        )
        load_handler = make_phase3_http_handler(
            lambda: secret, lambda: load_runner, lambda: result_secret,
        )
        load_server = ThreadingHTTPServer(("127.0.0.1", 0), load_handler)
        load_thread = threading.Thread(target=load_server.serve_forever, daemon=True)
        load_thread.start()
        try:
            load_url = f"http://127.0.0.1:{load_server.server_port}/v1/epsilon/phase3/run"

            def send_load(item):
                execution_key = "schedule:1800000000"
                raw_body = json.dumps({
                    "automation_id": item["automation_id"],
                    "execution_key": execution_key,
                }, separators=(",", ":")).encode()
                sent_at = str(int(time.time()))
                request = Request(load_url, data=raw_body, headers={
                    "Content-Type": "application/json",
                    "X-HADES-Timestamp": sent_at,
                    "X-HADES-Signature": sign_request(secret, sent_at, raw_body),
                }, method="POST")
                with urlopen(request, timeout=12) as response:
                    return item, raw_body, sent_at, json.loads(response.read())

            with ThreadPoolExecutor(max_workers=10) as pool:
                completed = list(pool.map(send_load, load_items))
            outcomes = {
                row[0]["resource_scope"][0].removesuffix(".health"): row[3]
                for row in completed
            }
            for resource in load_resources:
                expected_status = "FAILED" if resource == "synthetic-core-9" else "COMPLETE"
                assert outcomes[resource]["status"] == expected_status, (resource, outcomes[resource])
            assert "synthetic private source detail" not in json.dumps(outcomes)
            assert load_reads == Counter({resource: 1 for resource in load_resources}), load_reads

            def replay_load(completed_row):
                item, raw_body, sent_at, _first = completed_row
                request = Request(load_url, data=raw_body, headers={
                    "Content-Type": "application/json",
                    "X-HADES-Timestamp": sent_at,
                    "X-HADES-Signature": sign_request(secret, sent_at, raw_body),
                }, method="POST")
                with urlopen(request, timeout=12) as response:
                    return item, json.loads(response.read())

            with ThreadPoolExecutor(max_workers=10) as pool:
                replays = list(pool.map(replay_load, completed))
            for item, replay in replays:
                assert replay["replayed"] is True, replay
                expected_status = "FAILED" if item["resource_scope"] == ["synthetic-core-9.health"] else "COMPLETE"
                assert replay["status"] == expected_status, replay
            assert load_reads == Counter({resource: 1 for resource in load_resources}), load_reads
            with sqlite3.connect(load_store.path) as db:
                assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert db.execute("SELECT COUNT(*) FROM phase3_runs").fetchone()[0] == 10
        finally:
            load_server.shutdown()
            load_server.server_close()
            load_thread.join(timeout=3)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

print("PASS authenticated Phase 3 run request: HTTP path, signed body, freshness, strict schema, and durable retry idempotency")
print("PASS bounded Phase 3 load: ten concurrent maximum-quota runs; source failure redaction and replay; one read per execution key; SQLite integrity")
PY
