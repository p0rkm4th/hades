#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
PYTHONPATH="$repo_dir" python3 - <<'PY'
import json
from pathlib import Path

config = json.loads(Path("config/decision-shadow.json").read_text())
assert config["schema"] == "hades-decision-shadow-config/v1"
assert config["enabled"] is False
assert config["candidate"] is None
assert config["mode"] == "replay_only"
assert config["fallback"] == "CURRENT"
assert config["max_sample_rate"] == 0.0
assert config["production_steering"] is False
assert config["record_raw_request"] is False
assert config["record_raw_context"] is False
print("PASS Decision Plane shadow configuration is disabled and fail-safe")
PY
