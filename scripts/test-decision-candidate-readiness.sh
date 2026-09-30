#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
output="$(PYTHONPATH="$repo_dir" python3 scripts/inspect-decision-candidates.py)"
printf '%s\n' "$output" | PYTHONPATH="$repo_dir" python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["schema"] == "hades-decision-candidate-readiness/v1"
assert len(d["candidates"]) == 5
for candidate in d["candidates"]:
    assert candidate["quality"] in {"control_only", "not_measured"}
    assert candidate["privacy_boundary"] in {"local_only", "synthetic_or_public_only"}
print("PASS candidate readiness is explicit and no quality is overstated")
'
