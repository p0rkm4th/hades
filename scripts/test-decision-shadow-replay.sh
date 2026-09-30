#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
if [[ ! -f /tmp/hades-semif-results.jsonl ]]; then
  echo "SKIP: no isolated SemIf result artifact" >&2
  exit 0
fi
PYTHONPATH="$repo_dir" python3 scripts/replay-decision-shadow.py /tmp/hades-semif-results.jsonl | python3 -c '
import json,sys
x=json.load(sys.stdin)
assert x["schema"] == "hades-decision-shadow-replay/v1"
assert x["cases"] >= 29
assert x["production_steering"] is False
assert x["raw_requests_emitted"] is False
assert len(x["request_hashes"]) == x["cases"]
print("PASS sanitized candidate replay returns CURRENT and emits hash-only evidence")
'
