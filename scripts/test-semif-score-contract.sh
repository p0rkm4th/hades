#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
if [[ ! -f /tmp/hades-semif-results.jsonl ]]; then
  echo "SKIP: no isolated SemIf result artifact" >&2
  exit 0
fi
PYTHONPATH="$repo_dir" python3 scripts/score-semif-results.py /tmp/hades-semif-results.jsonl | python3 -c '
import json,sys
x=json.load(sys.stdin)
assert x["schema"] == "hades-decision-semif-score/v1"
assert x["cases"] == 29
assert 0 <= x["accuracy"] <= 1
assert x["brier"] >= 0
assert x["nll"] >= 0
assert 0 <= x["ece_10_bins"] <= 1
print("PASS reproducible SemIf score contract")
'
