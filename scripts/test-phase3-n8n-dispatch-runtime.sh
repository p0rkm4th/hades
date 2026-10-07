#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

image=${HADES_N8N_IMAGE:-docker.n8n.io/n8nio/n8n@sha256:9c0862a08090c79122069e23131d27529c250b92e90c9d51a6ec406fe1527c4e}
[[ "$image" =~ ^[^[:space:]=]+@sha256:[0-9a-f]{64}$ ]] || {
  echo 'FAIL HADES_N8N_IMAGE must be an immutable image digest' >&2
  exit 2
}

python3 - "$PWD" "$image" <<'PY'
import hashlib
import hmac
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
image = sys.argv[2]
secret = b"synthetic-n8n-runner-hmac-key-at-least-32-bytes"
expected = []
failures = []
now = int(time.time())
due_polls = 0
run_calls = []
due_records = [
    {"automation_id": "p3-a1b2c3d4", "execution_key": f"schedule:{now}", "due_at": now},
    {"automation_id": "p3-e5f6g7h8", "execution_key": f"schedule:{now}", "due_at": now},
]

gateway = subprocess.run(
    ["docker", "network", "inspect", "bridge", "--format", "{{(index .IPAM.Config 0).Gateway}}"],
    text=True, capture_output=True, check=True,
).stdout.strip()
socket.inet_aton(gateway)

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        global due_polls
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        timestamp = self.headers.get("X-HADES-Timestamp", "")
        signature = self.headers.get("X-HADES-Signature", "")
        expected_signature = hmac.new(
            secret,
            b"POST\n" + self.path.encode() + b"\n" + timestamp.encode() + b"\n" + body,
            hashlib.sha256,
        ).hexdigest()
        if not timestamp.isdigit() or abs(int(timestamp) - int(time.time())) > 120 or not hmac.compare_digest(signature, expected_signature):
            failures.append("signature or timestamp rejected")
            self.send_error(401)
            return
        try:
            value = json.loads(body)
        except json.JSONDecodeError:
            failures.append("invalid request JSON")
            self.send_error(400)
            return
        if self.path == "/v1/epsilon/phase3/due":
            if body != b"{}" or value != {}:
                failures.append("due request body differed from fixed contract")
                self.send_error(400)
                return
            due_polls += 1
            expected.extend(row["automation_id"] for row in due_records)
            result = {"due": due_records}
        elif self.path == "/v1/epsilon/phase3/run":
            if (
                not isinstance(value, dict)
                or set(value) != {"automation_id", "execution_key"}
                or value.get("automation_id") not in expected
                or not re.fullmatch(r"schedule:[0-9]{10}", str(value.get("execution_key", "")))
            ):
                failures.append("run request was outside the fixed contract")
                self.send_error(400)
                return
            run_calls.append(value["automation_id"])
            result = {"status": "COMPLETE", "result": {"hades_state": "READY"}}
        else:
            failures.append("unexpected endpoint")
            self.send_error(404)
            return
        raw = json.dumps(result, separators=(",", ":")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args):
        return

server = ThreadingHTTPServer((gateway, 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with tempfile.TemporaryDirectory(prefix="hades-phase3-n8n-runtime-") as raw_tmp:
        tmp = Path(raw_tmp)
        data = tmp / "data"
        data.mkdir(mode=0o700)
        workflow = json.loads((repo / "config/epsilon-workflows/phase3-runner-dispatch.json").read_text())
        # n8n's CLI starts workflows from a trigger; replace the fixed timer
        # with Manual Trigger only in this disposable runtime fixture.
        for node in workflow["nodes"]:
            if node["name"] == "Every five minutes":
                node["type"] = "n8n-nodes-base.manualTrigger"
                node["typeVersion"] = 1
                node["parameters"] = {}
        for node in workflow["nodes"]:
            if node["type"] == "n8n-nodes-base.crypto":
                node["credentials"]["crypto"]["id"] = "synthetic-phase3-crypto"
            if node["type"] == "n8n-nodes-base.httpRequest":
                node["parameters"]["url"] = node["parameters"]["url"].replace(
                    "host.docker.internal:8643", f"host.docker.internal:{server.server_port}",
                )
        cred_path = tmp / "credentials.json"
        cred_path.write_text(json.dumps([{
            "id": "synthetic-phase3-crypto",
            "name": "HADES Phase3 Runner HMAC",
            "type": "crypto",
            "data": {"hmacSecret": secret.decode()},
        }]))
        cred_path.chmod(0o600)
        workflow_path = tmp / "workflow.json"
        workflow_path.write_text(json.dumps(workflow))
        workflow_path.chmod(0o600)
        encryption_key = "synthetic-n8n-instance-encryption-key-for-test-only"
        base = [
            "docker", "run", "--rm", "--network", "bridge",
            "--add-host", "host.docker.internal:host-gateway",
            "-v", f"{data}:/home/node/.n8n",
            "-e", f"N8N_ENCRYPTION_KEY={encryption_key}",
            "-e", "N8N_USER_FOLDER=/home/node",
            image,
        ]
        for path, mount in ((cred_path, "/tmp/credentials.json"), (workflow_path, "/tmp/workflow.json")):
            mount_spec = f"{path}:{mount}:ro"
            # Keep the synthetic credential import and workflow execution on a
            # one-shot container using only this test's temporary data volume.
            command = base[:3] + ["-v", mount_spec] + base[3:]
            if mount == "/tmp/credentials.json":
                command += ["import:credentials", "--input=" + mount]
            else:
                command += ["import:workflow", "--input=" + mount]
            result = subprocess.run(command, capture_output=True, text=True, timeout=120)
            if result.returncode:
                raise RuntimeError("pinned n8n fixture import failed")
        command = base + ["execute", "--id=hades-phase3-runner-dispatch", "--rawOutput"]
        execution = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if execution.returncode:
            raise RuntimeError("pinned n8n fixed dispatcher execution failed")
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)

if failures:
    raise SystemExit("FAIL pinned n8n dispatcher runtime: " + "; ".join(failures))
if due_polls != 1 or sorted(run_calls) != ["p3-a1b2c3d4", "p3-e5f6g7h8"]:
    raise SystemExit("FAIL pinned n8n dispatcher runtime: due batch or run count differed")
print("PASS pinned n8n dispatcher runtime: Crypto credential, canonical HMAC, due poll, and fixed signed run dispatch")
PY
