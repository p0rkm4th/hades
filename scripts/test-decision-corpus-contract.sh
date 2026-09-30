#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
PYTHONPATH="$repo_dir" python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("test-data/decision-corpus-v1/corpus.json").read_text())
assert data["schema"] == "hades-decision-corpus/v1"
assert data["privacy_policy"] == "sanitized_only"
assert len(data["cases"]) >= 30
required = {"case_id", "source", "input", "expected", "authority_expectation", "privacy"}
seen = set()
for case in data["cases"]:
    assert required <= case.keys()
    assert case["case_id"] not in seen
    seen.add(case["case_id"])
    assert "intent" in case["expected"] or "capability_family" in case["expected"]
    assert case["privacy"] in {"public_synthetic", "household_synthetic", "synthetic_private", "synthetic_finance", "synthetic_infra", "synthetic_home"}
print(f"PASS sanitized HADES decision corpus v1 ({len(data['cases'])} cases)")
PY
