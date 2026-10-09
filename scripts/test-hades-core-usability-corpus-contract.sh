#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
corpus="$repo_root/benchmarks/hades-core-owner-corpus-v2.json"

python3 - "$corpus" <<'PY'
import json
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
assert data["schema_version"] == 2
cases = data["cases"]
assert 40 <= len(cases) <= 60, f"expected 40–60 cases, got {len(cases)}"
ids = [case["id"] for case in cases]
assert len(ids) == len(set(ids)), "case IDs must be unique"
required = {
    "ordinary", "conversation", "continuation", "memory", "grocy",
    "homelab", "research", "workspace", "coding", "agentic",
    "operator", "authority", "failure",
}
categories = {case["category"] for case in cases}
assert required <= categories, f"missing categories: {sorted(required - categories)}"
assert all(case.get("owner_preference") is None for case in cases)
coverage = data["replay_coverage"]
assert coverage["owner_preference_labels"] == 0
assert coverage["unreplayed_case_count"] == 29
assert len(coverage["chat_only_case_ids"]) + len(coverage["tool_backed_case_ids"]) + coverage["unreplayed_case_count"] == len(cases)
for case in cases:
    assert case["turns"] and all(isinstance(turn, str) and turn.strip() for turn in case["turns"])

reference_keys = {
    "metrics_record",
    "metrics_records",
    "report",
    "intermediate_failure_metrics_record",
}
references = set()

def collect_references(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in reference_keys:
                if isinstance(child, str):
                    references.add(child)
                elif isinstance(child, list):
                    references.update(item for item in child if isinstance(item, str))
            collect_references(child)
    elif isinstance(value, list):
        for child in value:
            collect_references(child)

collect_references(data)
repo_root = path.parent.parent.resolve()
for reference in references:
    target = (repo_root / reference).resolve()
    assert target.is_relative_to(repo_root), f"corpus reference escapes repository: {reference}"
    assert target.is_file(), f"corpus artifact reference is missing: {reference}"

serialized = path.read_text(encoding="utf-8")
assert not re.search(r"(?i)(sk-[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|password\s*[:=])", serialized)
print(f"PASS: {len(cases)} sanitized corpus cases across {len(categories)} categories; {len(references)} evidence references resolve; owner labels remain unassigned")
PY
