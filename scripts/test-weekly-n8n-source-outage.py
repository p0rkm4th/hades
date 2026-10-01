#!/usr/bin/env python3
"""Run the pinned weekly n8n graph against synthetic healthy and failed sources."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COUNTS: dict[str, int] = {"/groceries": 0, "/backup": 0, "/health": 0}
COUNTS_LOCK = threading.Lock()


class SourceFixture(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        pass

    def do_GET(self) -> None:
        with COUNTS_LOCK:
            if self.path in COUNTS:
                COUNTS[self.path] += 1
        if self.path == "/groceries":
            payload = {"error": "synthetic Grocy unavailable"}
            status = 503
        elif self.path == "/backup":
            payload = {"status": "HEALTHY", "result": "synthetic backup verified"}
            status = 200
        elif self.path == "/health":
            payload = {"status": True}
            status = 200
        else:
            payload = {"error": "not found"}
            status = 404
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def main() -> int:
    versions: dict[str, str] = {}
    for line in (ROOT / "config/versions.env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            versions[key.strip()] = value.strip().strip("\"'")
    image = os.environ.get(
        "HADES_N8N_IMAGE",
        versions.get(
            "HADES_N8N_IMAGE",
            "docker.n8n.io/n8nio/n8n@sha256:9f693fd5565539efd5e75ad168526c8041a6af516d9e50bc4d9cb1c9c5031523",
        ),
    )
    if not re.fullmatch(r"[^\s=]+@sha256:[0-9a-f]{64}", image):
        raise SystemExit("FAIL pinned HADES_N8N_IMAGE is not an immutable digest")
    inspected = run(["docker", "image", "inspect", image], timeout=15)
    if inspected.returncode:
        raise SystemExit("FAIL pinned n8n image is not present locally; refusing an implicit pull")

    gateway = run(
        ["docker", "network", "inspect", "bridge", "--format", "{{(index .IPAM.Config 0).Gateway}}"],
        timeout=10,
    ).stdout.strip()
    socket.inet_aton(gateway)
    server = ThreadingHTTPServer((gateway, 0), SourceFixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_port

    try:
        with tempfile.TemporaryDirectory(prefix="hades-weekly-n8n-outage-") as raw:
            work = Path(raw)
            work.chmod(0o700)
            data = work / "n8n-data"
            data.mkdir(mode=0o700)
            workflow = json.loads(
                (ROOT / "config/epsilon-workflows/weekly-household-summary-n8n.json").read_text()
            )
            workflow["id"] = "weekly-source-outage-fixture"
            workflow["active"] = False
            schedule_name = "Bounded weekly schedule"
            workflow["nodes"] = [
                node for node in workflow["nodes"] if node.get("name") != schedule_name
            ]
            workflow["connections"].pop(schedule_name, None)
            trigger = next(
                node for node in workflow["nodes"] if node.get("name") == "HADES-local run-now trigger"
            )
            trigger["type"] = "n8n-nodes-base.manualTrigger"
            trigger["typeVersion"] = 1
            trigger["parameters"] = {}
            trigger.pop("webhookId", None)
            urls = {
                "Authorized Grocy result source": f"http://host.docker.internal:{port}/groceries",
                "Authorized backup result source": f"http://host.docker.internal:{port}/backup",
                "Authorized server health result source": f"http://host.docker.internal:{port}/health",
            }
            for node in workflow["nodes"]:
                if node.get("name") in urls:
                    node["parameters"]["url"] = urls[node["name"]]
            workflow_file = work / "workflow.json"
            workflow_file.write_text(json.dumps(workflow), encoding="utf-8")
            workflow_file.chmod(0o600)
            base = [
                "docker", "run", "--rm", "--network", "bridge",
                "--add-host", "host.docker.internal:host-gateway",
                "-v", f"{data}:/home/node/.n8n:Z",
                "-v", f"{workflow_file}:/tmp/weekly-workflow.json:ro,Z",
                "-e", "N8N_ENCRYPTION_KEY=synthetic-n8n-encryption-key-not-for-production",
                "-e", "N8N_USER_FOLDER=/home/node",
                "-e", "N8N_DIAGNOSTICS_ENABLED=false",
                image,
            ]
            imported = run(base + ["import:workflow", "--input=/tmp/weekly-workflow.json"])
            if imported.returncode:
                raise RuntimeError("pinned n8n workflow import failed: " + imported.stderr[-1600:])
            executed = run(base + ["execute", "--id=weekly-source-outage-fixture", "--rawOutput"])
            if executed.returncode:
                raise RuntimeError(
                    "weekly workflow failed when one source returned synthetic HTTP 503\n"
                    + executed.stdout[-2000:] + executed.stderr[-2000:]
                )
            with COUNTS_LOCK:
                counts = dict(COUNTS)
            if counts != {"/groceries": 1, "/backup": 1, "/health": 1}:
                raise RuntimeError(f"weekly n8n branch calls were incomplete: {counts}")
            output = executed.stdout + executed.stderr
            required_output = (
                "ERR_BAD_RESPONSE",
                '"status": 503',
                "synthetic backup verified",
                '"hades_state": "UP"',
            )
            missing = [marker for marker in required_output if marker not in output]
            if missing:
                raise RuntimeError(
                    "n8n execution did not preserve the HTTP 503 and healthy results; "
                    f"missing markers: {missing}\n" + output[-2500:]
                )
            print("PASS pinned n8n weekly workflow completes with synthetic Grocy HTTP 503")
            print("PASS backup and health sources still execute; health is projected as UP")
            print("PASS all three synthetic source branches were called exactly once")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
