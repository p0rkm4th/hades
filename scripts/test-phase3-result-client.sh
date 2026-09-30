#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError

from integrations.automation.phase3_request import sign_results_request
from integrations.automation.phase3_result_client import (
    Phase3ResultClient,
    Phase3ResultQueryError,
    is_phase3_results_intent,
    render_recent_results,
    actionable_notification_snapshot,
)

assert is_phase3_results_intent("How did my weekly household summary go?")
assert is_phase3_results_intent("What did our weekly household summary find?")
assert is_phase3_results_intent("show my latest grocery automation results")
assert is_phase3_results_intent("When were our backups last verified?")
assert is_phase3_results_intent("How old are the backups?")
assert is_phase3_results_intent("Are my backups up to date?")
assert is_phase3_results_intent("When did we last check the backups?")
assert not is_phase3_results_intent("how do I make a grocery list?")

route_source = Path("hermes/sitecustomize.py").read_text(encoding="utf-8")
assert "HADES_PHASE3_NOTIFICATION_FEED_V1" in route_source
assert "_hades_phase3_notification_feed(" in route_source
assert "actionable_notification_snapshot(rows)" in route_source
assert "HADES_PHASE3_NOTIFICATION_FEED_V1" in route_source[route_source.index("def _hades_nonpersonal_state_turn"):route_source.index("def _hades_transient_error_text")]
route_start = route_source.index("# Recent Phase 3 results are read")
route_end = route_source.index("            try:\n", route_start)
route_filter = route_source[route_start:route_end]
for gate in (
    r"\bwhen\s+(?:was|were)\s+",
    r"\bhow\s+old\s+",
    r"\b(?:are|is)\s+",
):
    assert gate in route_filter, f"Hermes result-route prefilter blocks {gate!r}"

rows = [{
    "template_type": "low-inventory-summary",
    "resource_scope": ["grocy.household"],
    "completed_at": 123456,
    "result": {"hades_state": "READY", "low": '["Rice", "Beans"]', "out": [], "no_minimum": []},
}, {
    "template_type": "server-health-watch",
    "resource_scope": ["hades-core.health"],
    "completed_at": 123455,
    "result": {"hades_state": "SOURCE_UNAVAILABLE", "reason": "private detail"},
}]
rendered = render_recent_results(rows)
assert "2 item(s) below minimum" in rendered and "Rice, Beans" in rendered
assert "couldn't confirm a result" in rendered
assert "run_id" not in rendered and "private detail" not in rendered
assert "no completed" in render_recent_results([]).casefold()

notifications = actionable_notification_snapshot([
    {"template_type": "server-health-watch", "resource_scope": ["hades-core.health"], "completed_at": 101,
     "result": {"hades_state": "UP"}},
    {"template_type": "low-inventory-summary", "resource_scope": ["grocy.household"], "completed_at": 99,
     "result": {"hades_state": "READY", "low": ["Milk", "Bread"], "out": ["Eggs"]}},
    {"template_type": "hades-backup-verification", "resource_scope": ["backup.evidence"], "completed_at": 98,
     "result": {"hades_state": "ATTENTION", "targets": [
         {"target": "hades", "hades_state": "HEALTHY"},
         {"target": "infra", "hades_state": "STALE", "custody": "/private/path"},
     ]}},
    {"template_type": "weekly-household-summary", "resource_scope": ["grocy.household", "backup.evidence"], "completed_at": 97,
     "result": {"hades_state": "PARTIAL", "sources": {"backup.evidence": {"hades_state": "SOURCE_UNAVAILABLE"}}}},
    {"template_type": "server-health-watch", "resource_scope": ["hades-core.health"], "completed_at": 100,
     "result": {"hades_state": "DOWN", "hades_reason": "private service diagnostic"}},
])
assert len(notifications) == 4
assert all(row["source_key"] and row["state_key"] for row in notifications)
assert [row["actionable"] for row in notifications] == [False, True, True, True]
assert "private" not in json.dumps(notifications).casefold()
assert "private/path" not in json.dumps(notifications)
assert "Milk" not in notifications[1]["message"] and "Eggs" not in notifications[1]["message"]  # push text uses counts without inventory item names
assert "2 item(s) below minimum and 1 out of stock" in notifications[1]["message"]
assert "infrastructure repository backup is stale" in notifications[2]["message"]
assert notifications[0]["title"] == "Server Health Watch"
assert "reported down" not in notifications[0]["message"]  # current healthy state supersedes old failure
latest_failure = actionable_notification_snapshot([
    {"template_type": "server-health-watch", "resource_scope": ["hades-core.health"], "completed_at": 202,
     "result": {"hades_state": "DOWN", "hades_reason": "private service diagnostic"}},
    {"template_type": "server-health-watch", "resource_scope": ["hades-core.health"], "completed_at": 201,
     "result": {"hades_state": "UP"}},
])[0]
assert latest_failure["actionable"] and "reported down" in latest_failure["message"]
repeat = actionable_notification_snapshot([
    {"template_type": "server-health-watch", "resource_scope": ["hades-core.health"], "completed_at": 200,
     "result": {"hades_state": "DOWN", "hades_reason": "different private diagnostic"}},
])[0]
assert repeat["source_key"] == latest_failure["source_key"] and repeat["state_key"] == latest_failure["state_key"]
recovered = actionable_notification_snapshot([
    {"template_type": "server-health-watch", "resource_scope": ["hades-core.health"], "completed_at": 203,
     "result": {"hades_state": "UP"}},
])[0]
assert recovered["source_key"] == latest_failure["source_key"] and recovered["state_key"] != latest_failure["state_key"]

backup_result = render_recent_results([{
    "template_type": "hades-backup-verification",
    "resource_scope": ["backup.evidence"],
    "completed_at": 1790270000,
    "result": {
        "hades_state": "ATTENTION",
        "last_success_by_target": {
            "hades": {"checked_at": 1790270000, "artifact_mtime": 1790209800.0},
            "infra": {"checked_at": 1790200000, "artifact_mtime": 1790000000.0},
        },
        "targets": [
            {"target": "hades", "hades_state": "HEALTHY", "artifact_mtime": 1790209800,
             "observed_at": 1790270000, "git_bundle_verified": True,
             "label": "private backend label must not appear"},
            {"target": "infra", "hades_state": "STALE", "artifact_mtime": 1790000000,
             "observed_at": 1790270000, "custody": "/private/path/must/not/appear"},
            {"target": "unknown-secret-target", "hades_state": "HEALTHY",
             "artifact_mtime": 1790270000},
        ],
    },
}])
assert "HADES repository backup: healthy" in backup_result, backup_result
assert "verified copy dated 2026-09-24 00:30 UTC" in backup_result, backup_result
assert "infrastructure repository backup: stale; needs attention" in backup_result, backup_result
assert "last successful check 2026-09-24 17:13 UTC" in backup_result, backup_result
assert "verified copy dated 2026-09-21 14:13 UTC" in backup_result, backup_result
assert "last successful check 2026-09-23 21:46 UTC" in backup_result, backup_result
assert "latest check 2026-09-24 17:13 UTC" in backup_result, backup_result
assert "Repository backups:" in backup_result
assert "private backend label" not in backup_result and "/private/path" not in backup_result
assert "unknown-secret-target" not in backup_result
no_good_backup = render_recent_results([{
    "template_type": "hades-backup-verification", "resource_scope": [],
    "completed_at": 1, "result": {"hades_state": "ATTENTION",
        "last_success_by_target": {}, "last_success_history_truncated": True,
        "targets": [{"target": "hades", "hades_state": "MISSING"}]},
}])
assert "no successful check found in the latest 100 results" in no_good_backup
malformed_backup = render_recent_results([{
    "template_type": "hades-backup-verification", "resource_scope": [],
    "completed_at": 1, "result": {"hades_state": "HEALTHY", "targets": [
        {"target": "hades", "hades_state": "HEALTHY", "artifact_mtime": 10**100},
    ]},
}])
assert "verified copy dated" not in malformed_backup
untrusted_target = render_recent_results([{
    "template_type": "hades-backup-verification", "resource_scope": [],
    "completed_at": 1, "result": {"hades_state": "HEALTHY", "targets": [
        {"target": [], "hades_state": "HEALTHY", "artifact_mtime": 10},
        {"target": "not-allowlisted", "hades_state": "HEALTHY", "artifact_mtime": 10},
    ]},
}])
assert "recognized target statuses" in untrusted_target

with tempfile.TemporaryDirectory(prefix="hades-phase3-result-client-") as tmp:
    key_path = Path(tmp) / "query.key"
    key = b"distinct-hades-result-query-key-material-32-bytes"
    key_path.write_bytes(key)
    key_path.chmod(0o600)

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self, _limit):
            return json.dumps({"results": rows}).encode()

    captured = {}
    def opener(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    client = Phase3ResultClient(
        "http://127.0.0.1:8643/v1/epsilon/phase3/results", str(key_path), opener=opener,
    )
    assert client.recent_for("synthetic-alpha") == rows
    request = captured["request"]
    body = request.data
    assert json.loads(body) == {"requester_subject_id": "synthetic-alpha"}
    assert request.get_header("X-hades-signature") == sign_results_request(
        key, request.get_header("X-hades-timestamp"), body,
    )
    assert captured["timeout"] <= 4

    key_path.chmod(0o640)
    try:
        client.recent_for("synthetic-alpha")
    except Phase3ResultQueryError:
        pass
    else:
        raise AssertionError("client accepted a query key with unsafe permissions")

    try:
        Phase3ResultClient("http://example.com/v1/epsilon/phase3/results", str(key_path))
    except Phase3ResultQueryError:
        pass
    else:
        raise AssertionError("client accepted a remote plaintext result endpoint")

    key_path.chmod(0o600)
    paths = []
    class RedirectHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            paths.append(self.path)
            self.send_response(307)
            self.send_header("Location", "/capture")
            self.end_headers()
        def log_message(self, *_args):
            return
    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        redirected = Phase3ResultClient(
            f"http://127.0.0.1:{server.server_port}/v1/epsilon/phase3/results", str(key_path),
        )
        try:
            redirected.recent_for("synthetic-alpha")
        except Phase3ResultQueryError:
            pass
        else:
            raise AssertionError("client followed a result-query redirect")
        assert paths == ["/v1/epsilon/phase3/results"], paths
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    def denied(_request, timeout):
        raise HTTPError("http://127.0.0.1/", 403, "denied", {}, None)
    key_path.chmod(0o600)
    try:
        Phase3ResultClient(
            "http://127.0.0.1:8643/v1/epsilon/phase3/results", str(key_path), opener=denied,
        ).recent_for("synthetic-alpha")
    except Phase3ResultQueryError as exc:
        assert "current account" in str(exc)
    else:
        raise AssertionError("client hid a revoked-authority response")

print("PASS Phase 3 result client: explicit intent, bounded rendering, authenticated requester, private key, local endpoint, and failure honesty")
PY
