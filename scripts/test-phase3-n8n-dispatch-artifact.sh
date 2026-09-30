#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
import os
import subprocess
import tempfile
from pathlib import Path

workflow_path = Path("config/epsilon-workflows/phase3-runner-dispatch.json")
workflow = json.loads(workflow_path.read_text())
assert workflow["id"] == "hades-phase3-runner-dispatch" and workflow["active"] is False
assert workflow["settings"]["saveDataErrorExecution"] == "none"
assert workflow["settings"]["saveDataSuccessExecution"] == "none"
nodes = {node["name"]: node for node in workflow["nodes"]}
assert len(nodes) == 7
assert {node["type"] for node in nodes.values()} == {
    "n8n-nodes-base.scheduleTrigger", "n8n-nodes-base.code",
    "n8n-nodes-base.crypto", "n8n-nodes-base.httpRequest",
}
assert nodes["Every five minutes"]["parameters"]["rule"]["interval"][0]["minutesInterval"] == 5
crypto_nodes = [node for node in nodes.values() if node["type"] == "n8n-nodes-base.crypto"]
assert len(crypto_nodes) == 2
assert all(node["parameters"]["action"] == "hmac" and node["parameters"]["type"] == "SHA256" for node in crypto_nodes)
assert all(node["credentials"]["crypto"]["id"] == "CREDENTIAL_ID_REQUIRED" for node in crypto_nodes)
assert len({node["credentials"]["crypto"]["name"] for node in crypto_nodes}) == 1
http_nodes = [node for node in nodes.values() if node["type"] == "n8n-nodes-base.httpRequest"]
assert {node["parameters"]["url"] for node in http_nodes} == {
    "http://host.docker.internal:8643/v1/epsilon/phase3/due",
    "http://host.docker.internal:8643/v1/epsilon/phase3/run",
}
assert all(node["parameters"]["method"] == "POST" and node["parameters"]["contentType"] == "raw" for node in http_nodes)
code = "\n".join(node["parameters"]["jsCode"] for node in nodes.values() if node["type"] == "n8n-nodes-base.code")
assert "process.env" not in code and "require(" not in code and "fetch(" not in code
assert "phase3/due" in code and "phase3/run" in code and "due.length > 25" in code
for source, branches in workflow["connections"].items():
    assert source in nodes
    for branch in branches["main"]:
        for connection in branch:
            assert connection["node"] in nodes

renderer = Path("scripts/render-phase3-dispatch-workflow.py").resolve()
with tempfile.TemporaryDirectory(prefix="hades-phase3-workflow-render-") as tmp:
    output = Path(tmp) / "rendered.json"
    subprocess.run(
        ["python3", str(renderer), "--credential-id", "credential-test-1234", "--output", str(output)],
        check=True, capture_output=True, text=True,
    )
    rendered = json.loads(output.read_text())
    assert all(
        node["credentials"]["crypto"]["id"] == "credential-test-1234"
        for node in rendered["nodes"] if node["type"] == "n8n-nodes-base.crypto"
    )
    assert not (output.stat().st_mode & 0o077)
    reused = subprocess.run(
        ["python3", str(renderer), "--credential-id", "credential-test-1234", "--output", str(output)],
        capture_output=True, text=True,
    )
    assert reused.returncode != 0

print("PASS Phase 3 n8n dispatcher artifact: fixed signed endpoints, encrypted credential reference, no execution-data persistence, inactive by default")
PY
