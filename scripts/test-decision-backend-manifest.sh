#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
PYTHONPATH="$repo_dir" python3 - <<'PY'
import json
from pathlib import Path

path = Path("config/decision-backends.json")
data = json.loads(path.read_text())
assert data["schema"] == "hades-decision-backends/v1"
names = [item["name"] for item in data["candidates"]]
assert names == ["CURRENT", "Jev", "SemIf-Qwen3.5-4B", "NanoJev", "GLiClass"]
assert len(names) == len(set(names))
for item in data["candidates"]:
    for key in ("kind", "status", "source", "revision", "score_semantics", "privacy_boundary", "supported_decisions", "runtime_status"):
        assert key in item, (item["name"], key)
    assert item["privacy_boundary"] in {"local_only", "synthetic_or_public_only"}
assert data["candidates"][0]["runtime_status"] == "available"
assert all(item["status"] != "production" for item in data["candidates"][1:])
assert data["candidates"][1]["status"] == "research_only"
assert data["candidates"][2]["status"] == "evaluated_not_qualified"
assert data["candidates"][3]["status"] == "deferred_domain_mismatch"
assert data["candidates"][4]["status"] == "evaluated_not_qualified"
print("PASS decision backend manifest is pinned and non-promotional")
PY
