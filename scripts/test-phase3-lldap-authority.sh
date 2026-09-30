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

from integrations.automation.phase3_lldap_authority import Phase3LldapAuthority
from integrations.automation.phase3_self_service import Phase3AuthorizationError

policy_doc = " ".join(Path("docs/phase3-authority-policy.md").read_text(encoding="utf-8").split())
for required in (
    "no active/disabled field",
    "remove the user's mapped HADES authorization",
    "disposable acceptance target",
    "Do not treat disabling only the Open WebUI account as revocation",
):
    assert required in policy_doc, f"directory revocation procedure is missing: {required}"


class Directory:
    groups = {"hades-owner"}
    reader_groups = {"lldap_strict_readonly"}
    requests = 0
    fail_graphql = False


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        Directory.requests += 1
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        if self.path == "/auth/simple/login":
            result = {"token": "synthetic-reader-token"} if body == {
                "username": "hades-phase3-reader", "password": "synthetic-password",
            } else {"error": "invalid"}
            status = 200 if "token" in result else 401
        elif self.path == "/api/graphql":
            assert self.headers.get("Authorization") == "Bearer synthetic-reader-token"
            if Directory.fail_graphql:
                result, status = {"errors": [{"message": "synthetic outage"}]}, 200
            else:
                variables = body["variables"]
                result, status = {"data": {
                    "reader": {"id": variables["readerId"], "groups": [{"displayName": name} for name in sorted(Directory.reader_groups)]},
                    "subject": {"id": variables["subjectId"], "groups": [{"displayName": name} for name in sorted(Directory.groups)]},
                }}, 200
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


def expect_denied(call, phrase="current directory authority"):
    try:
        call()
    except Phase3AuthorizationError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("unsafe or unavailable directory authority was accepted")


with tempfile.TemporaryDirectory(prefix="hades-phase3-lldap-authority-") as tmp:
    root = Path(tmp)
    config = root / "authority.json"
    password = root / "reader-password"
    value = {
        "schema": 1,
        "reader_user_id": "hades-phase3-reader",
        "subjects": {"stable-webui-subject": "directory-alpha"},
        "groups": {
            "hades-owner": {"role": "owner", "resources": ["hades-core.health", "grocy.household"]},
            "hades-household": {"role": "household", "resources": ["grocy.household"]},
        },
    }
    config.write_text(json.dumps(value), encoding="utf-8")
    config.chmod(0o600)
    password.write_text("synthetic-password\n", encoding="utf-8")
    password.chmod(0o600)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        resolver = Phase3LldapAuthority(config, password, f"http://127.0.0.1:{server.server_port}")
        owner = resolver("stable-webui-subject")
        assert owner.subject == "stable-webui-subject" and owner.role == "owner"
        assert owner.active and owner.resources == frozenset({"hades-core.health", "grocy.household"})
        assert Directory.requests == 2, "lookup should authenticate and fetch live membership without caching"

        Directory.groups = {"hades-household"}
        household = resolver("stable-webui-subject")
        assert household.role == "household" and household.resources == frozenset({"grocy.household"})
        assert Directory.requests == 4, "changed membership should be observed on the next lookup"

        before_unknown = Directory.requests
        unknown = resolver("unmapped-subject")
        assert not unknown.active and not unknown.resources
        assert Directory.requests == before_unknown, "unmapped subject reached the directory"

        Directory.groups = {"hades-owner"}
        Directory.reader_groups = {"lldap_admin", "lldap_strict_readonly"}
        expect_denied(lambda: resolver("stable-webui-subject"), "least-privilege")
        Directory.reader_groups = {"lldap_strict_readonly"}

        Directory.fail_graphql = True
        expect_denied(lambda: resolver("stable-webui-subject"))
        Directory.fail_graphql = False

        password.chmod(0o644)
        expect_denied(lambda: resolver("stable-webui-subject"))
        password.chmod(0o600)
        config.chmod(0o644)
        expect_denied(lambda: resolver("stable-webui-subject"))
        config.chmod(0o600)

        unsafe = dict(value)
        unsafe["groups"] = {"hades-owner": {"role": "owner", "resources": ["finance.write"]}}
        config.write_text(json.dumps(unsafe), encoding="utf-8")
        config.chmod(0o600)
        expect_denied(lambda: resolver("stable-webui-subject"))

        unsafe = dict(value)
        unsafe["subjects"] = {"stable-webui-subject": "hades-phase3-reader"}
        config.write_text(json.dumps(unsafe), encoding="utf-8")
        config.chmod(0o600)
        expect_denied(lambda: resolver("stable-webui-subject"))

        unsafe = dict(value)
        unsafe["groups"] = {"lldap_admin": {"role": "owner", "resources": ["hades-core.health"]}}
        config.write_text(json.dumps(unsafe), encoding="utf-8")
        config.chmod(0o600)
        expect_denied(lambda: resolver("stable-webui-subject"))

        try:
            Phase3LldapAuthority(config, password, "http://directory.example:17170")
        except ValueError:
            pass
        else:
            raise AssertionError("remote plain HTTP directory endpoint was accepted")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

print("PASS Phase 3 live LLDAP authority contract: uncached membership, least-privilege reader, strict mapping/grants, unsafe-input and outage fail-closed")
PY
