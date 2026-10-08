#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
corpus="$repo_root/test-data/hades-core-usability-v1/corpus.json"

python3 - "$corpus" <<'PY'
import json
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
assert data["schema_version"] == "hades-core-usability-corpus/v1"
assert data["status"] == "candidate_for_owner_review"
assert data["owner_preference"] == "unrated"
cases = data["cases"]
assert 40 <= len(cases) <= 60, f"expected 40–60 cases, got {len(cases)}"
ids = [case["id"] for case in cases]
assert len(ids) == len(set(ids)), "case IDs must be unique"
required = {
    "ordinary_chat", "memory", "household", "homelab", "research",
    "workspace_coding", "operator_computer_use", "multi_user_isolation",
    "failure_and_recovery",
}
categories = {case["category"] for case in cases}
assert required <= categories, f"missing categories: {sorted(required - categories)}"
for case in cases:
    assert isinstance(case["turns"], list) and case["turns"]
    assert all(isinstance(turn, str) and turn.strip() for turn in case["turns"])
    expected = case["expected"]
    assert isinstance(expected["capabilities"], list)
    assert expected["must"].strip() and expected["must_not"].strip()
serialized = path.read_text(encoding="utf-8")
assert not re.search(r"(?i)(sk-[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|password\s*[:=])", serialized)
assert "https://example.invalid/" in serialized
print(f"PASS: {len(cases)} synthetic usability cases across {len(categories)} categories")
PY
