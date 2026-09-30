#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$repo_dir/config/epsilon-workflows/weekly-household-summary.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    workflow = json.load(handle)

assert workflow["status"] == "PREPARATION_ONLY"
assert workflow["runner"] == "n8n"
assert workflow["writes"] == []
assert workflow["requires_approval"] is True
assert workflow["inputs"]["week_start"]["maximum_window_days"] == 7
assert "private_finance" in workflow["excluded"]
assert "homelab_mutation" in workflow["excluded"]
assert workflow["idempotency"]["duplicate_behavior"] == "return_existing_summary"
assert workflow["failure_behavior"]["timeout"] == "outcome_unknown_without_claiming_success"
print("PASS Epsilon workflow is read-only and approval-gated")
print("PASS Epsilon workflow excludes private and privileged domains")
print("PASS Epsilon workflow has bounded idempotency and failure semantics")
PY
