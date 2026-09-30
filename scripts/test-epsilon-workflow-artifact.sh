#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONPATH="$repo_dir" python3 - <<'PY'
import json
from pathlib import Path

path = Path("config/epsilon-workflows/server-health-watch.json")
workflow = json.loads(path.read_text())
assert workflow["id"] == "epsilon-server-health-watch-core"
assert workflow["active"] is False
assert workflow["tags"] == [
    {"name": "hades-template:shw"},
    {"name": "hades-owner:owner"},
    {"name": "hades-approved:true"},
    {"name": "hades-trigger:schedule"},
]

allowed_types = {
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.code",
    "n8n-nodes-base.webhook",
}
nodes = {node["name"]: node for node in workflow["nodes"]}
assert nodes
assert {node["type"] for node in nodes.values()} <= allowed_types
assert all("credentials" not in node for node in nodes.values())
source = nodes["Authorized HADES Core health source"]
assert source["parameters"]["url"] == "http://hades-core.invalid/health"
assert source["parameters"]["options"]["timeout"] == 5000
assert source["onError"] == "continueRegularOutput"
assert nodes["Bounded 10-minute schedule"]["parameters"]["rule"]["interval"][0]["minutesInterval"] == 10
assert nodes["HADES-local run-now trigger"]["parameters"]["path"] == "epsilon-server-health-watch-core"
classifier = nodes["Classify and deduplicate bounded result"]
assert "getWorkflowStaticData" in classifier["parameters"]["jsCode"]
assert "hades_transition" in classifier["parameters"]["jsCode"]
assert "hades_notification" in classifier["parameters"]["jsCode"]

for source_name, branches in workflow["connections"].items():
    assert source_name in nodes
    for branch in branches["main"]:
        for connection in branch:
            assert connection["node"] in nodes

print("PASS inactive Epsilon workflow artifact is bounded and credential-free")
PY
