#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
output="$(PYTHONPATH="$repo_dir" python3 scripts/export-semif-corpus.py)"
printf '%s\n' "$output" | PYTHONPATH="$repo_dir" python3 -c '
import json, sys
rows = [json.loads(line) for line in sys.stdin if line.strip()]
assert len(rows) == 29
assert all("expected" in row and len(row["options"]) == 9 for row in rows)
assert all("authority_expectation" not in row and "privacy" not in row for row in rows)
print("PASS sanitized SemIf export (29 scalar family cases)")
'
