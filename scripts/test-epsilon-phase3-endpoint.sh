#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import importlib.util
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from integrations.automation.phase3_request import sign_request, sign_results_request
from integrations.automation.phase3_self_service import Phase3Authority, Phase3Catalog, Phase3Service, Phase3Store

owner = Phase3Authority("synthetic-owner", "owner", frozenset({"grocy.household"}))
recipient = Phase3Authority("synthetic-recipient", "household", frozenset({"grocy.household"}))

class DirectoryState:
    groups = {
        "directory-owner": {"hades-owner"},
        "directory-recipient": {"hades-household"},
    }


class DirectoryHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        if self.path == "/auth/simple/login":
            result = {"token": "synthetic-readonly-token"} if body == {
                "username": "phase3-reader", "password": "synthetic-directory-password",
            } else {"error": "unauthorized"}
            status = 200 if "token" in result else 401
        elif self.path == "/api/graphql":
            assert self.headers.get("Authorization") == "Bearer synthetic-readonly-token"
            ids = body["variables"]
            result = {"data": {
                "reader": {"id": ids["readerId"], "groups": [{"displayName": "lldap_strict_readonly"}]},
                "subject": {"id": ids["subjectId"], "groups": [{"displayName": name} for name in sorted(DirectoryState.groups.get(ids["subjectId"], set()))]},
            }}
            status = 200
        else:
            result, status = {"error": "not found"}, 404
        raw = json.dumps(result).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args):
        return


with tempfile.TemporaryDirectory(prefix="hades-epsilon-phase3-") as tmp:
    root = Path(tmp)
    state_path = root / "phase3.sqlite"
    authority_path = root / "directory-authority.json"
    password_path = root / "directory-reader-password"
    key_path = root / "runner.key"
    result_key_path = root / "result-query.key"
    provenance_path = root / "hades-live-provenance.json"
    authority_path.write_text(json.dumps({
        "schema": 1,
        "reader_user_id": "phase3-reader",
        "subjects": {owner.subject: "directory-owner", recipient.subject: "directory-recipient"},
        "groups": {
            "hades-owner": {"role": "owner", "resources": ["grocy.household"]},
            "hades-household": {"role": "household", "resources": ["grocy.household"]},
        },
    }), encoding="utf-8")
    authority_path.chmod(0o600)
    password_path.write_text("synthetic-directory-password\n", encoding="utf-8")
    password_path.chmod(0o600)
    secret = b"synthetic-phase3-runner-secret-at-least-32-bytes"
    key_path.write_bytes(secret)
    key_path.chmod(0o600)
    result_secret = b"synthetic-hades-result-secret-at-least-32-bytes"
    result_key_path.write_bytes(result_secret)
    result_key_path.chmod(0o600)
    provenance_path.write_text(json.dumps({
        "schema": "hades/deployed-provenance/v1",
        "hades_tree_sha256": "b" * 40,
        "infra_tree_sha256": "c" * 40,
        "hermes_runtime_kind": "python-module",
        "hermes_executable_sha256": "d" * 64,
        "hermes_profile_sha256": "e" * 64,
        "mcp_runtime_sha256": "f" * 64,
        "mcp_runtime": [{"name": "receipt-ocr-gateway", "endpoint": "http://private.test.invalid/mcp"}],
        "epsilon_package_manifest_sha256": "a" * 64,
        "private_test_value": "must-not-be-returned",
    }), encoding="utf-8")
    provenance_path.chmod(0o600)

    directory_server = ThreadingHTTPServer(("127.0.0.1", 0), DirectoryHandler)
    directory_thread = threading.Thread(target=directory_server.serve_forever, daemon=True)
    directory_thread.start()

    for name, value in {
        "HADES_EPSILON_PHASE3_STATE_FILE": str(state_path),
        "HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE": str(authority_path),
        "HADES_EPSILON_PHASE3_LLDAP_URL": f"http://127.0.0.1:{directory_server.server_port}",
        "HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE": str(password_path),
        "HADES_EPSILON_PHASE3_HMAC_KEY_FILE": str(key_path),
        "HADES_EPSILON_PHASE3_RESULT_HMAC_KEY_FILE": str(result_key_path),
        "HADES_DEPLOYED_PROVENANCE_FILE": str(provenance_path),
    }.items():
        os.environ[name] = value
    os.environ.pop("HADES_EPSILON_PHASE3_AUTHORITY_POLICY_FILE", None)

    spec = importlib.util.spec_from_file_location("epsilon_source_server", "integrations/epsilon-source/server.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    public_provenance = module.provenance()
    assert public_provenance["epsilon_package_manifest_sha256"] == "a" * 64
    assert public_provenance["hermes_executable_sha256"] == "d" * 64
    assert public_provenance["hermes_profile_sha256"] == "e" * 64
    assert public_provenance["mcp_runtime_sha256"] == "f" * 64
    assert public_provenance["hermes_runtime_kind"] == "python-module"
    assert "private_test_value" not in public_provenance
    assert "mcp_runtime" not in public_provenance
    assert "private.test.invalid" not in json.dumps(public_provenance)

    store = Phase3Store(str(state_path))
    service = Phase3Service(store, Phase3Catalog())
    preview = service.preview(owner, "low-inventory-summary", {})
    item = service.confirm(owner, preview["preview_id"], preview["preview_hash"], "endpoint-fixture")
    store.share(owner, item["automation_id"], recipient)
    reads = []
    module.inventory = lambda: reads.append(True) or {"hades_state": "READY", "low": ["synthetic item"]}

    server = ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = json.dumps({"automation_id": item["automation_id"], "execution_key": "test-execution-key-000000000001"}, separators=(",", ":")).encode()
        timestamp = str(int(__import__("time").time()))
        signature = sign_request(secret, timestamp, body)
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/epsilon/phase3/run"

        def post(sig, body_value=body, path=endpoint):
            request = Request(path, data=body_value, headers={
                "Content-Type": "application/json",
                "X-HADES-Timestamp": timestamp,
                "X-HADES-Signature": sig,
            }, method="POST")
            return urlopen(request, timeout=3)

        with post(signature) as response:
            first = json.loads(response.read())
        with post(signature) as response:
            duplicate = json.loads(response.read())
        assert first["status"] == "COMPLETE" and first["result"]["low"] == ["synthetic item"]
        assert duplicate["replayed"] is True and len(reads) == 1

        result_body = json.dumps({
            "requester_subject_id": recipient.subject,
        }, separators=(",", ":")).encode()
        result_endpoint = f"http://127.0.0.1:{server.server_port}/v1/epsilon/phase3/results"
        result_timestamp = str(int(__import__("time").time()))
        result_request = Request(result_endpoint, data=result_body, headers={
            "Content-Type": "application/json",
            "X-HADES-Timestamp": result_timestamp,
            "X-HADES-Signature": sign_results_request(result_secret, result_timestamp, result_body),
        }, method="POST")
        with urlopen(result_request, timeout=3) as response:
            shared = json.loads(response.read())
        assert len(shared["results"]) == 1
        assert shared["results"][0]["result"]["low"] == ["synthetic item"]
        assert "run_id" not in shared["results"][0]

        wrong_result_credential = Request(result_endpoint, data=result_body, headers={
            "Content-Type": "application/json",
            "X-HADES-Timestamp": result_timestamp,
            "X-HADES-Signature": sign_request(secret, result_timestamp, result_body),
        }, method="POST")
        try:
            urlopen(wrong_result_credential, timeout=3)
        except HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("Epsilon accepted the n8n runner key for a result read")

        DirectoryState.groups["directory-recipient"].clear()
        with urlopen(result_request, timeout=3) as response:
            revoked = json.loads(response.read())
        assert revoked == {"results": []}, "Epsilon returned a shared result after LLDAP grant revocation"

        try:
            post("0" * 64)
        except HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("Epsilon endpoint accepted invalid signature")
        try:
            post(signature, path=endpoint + "/unknown")
        except HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("Epsilon endpoint accepted unknown path")

        DirectoryState.groups["directory-owner"].clear()
        body2 = json.dumps({"automation_id": item["automation_id"], "execution_key": "test-execution-key-000000000002"}, separators=(",", ":")).encode()
        try:
            post(sign_request(secret, timestamp, body2), body_value=body2)
        except HTTPError as exc:
            assert exc.code == 403
        else:
            raise AssertionError("Epsilon endpoint accepted revoked subject")
        assert len(reads) == 1, "revoked subject reached canonical inventory source"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        directory_server.shutdown()
        directory_server.server_close()
        directory_thread.join(timeout=3)

    for key in (
        "HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE",
        "HADES_EPSILON_PHASE3_LLDAP_URL",
        "HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE",
        "HADES_EPSILON_PHASE3_RESULT_HMAC_KEY_FILE",
    ):
        os.environ.pop(key, None)
    try:
        module._phase3_runner()
    except RuntimeError as exc:
        assert "live directory authority" in str(exc)
    else:
        raise AssertionError("Phase 3 runner accepted missing live authority inputs")

print("PASS Epsilon Phase 3 endpoint: authenticated dispatch, live directory revocation, fixed-source execution, and one-read idempotency")
PY
