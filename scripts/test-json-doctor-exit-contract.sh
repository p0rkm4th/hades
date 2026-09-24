#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

if "$repo_dir/scripts/hades" doctor --json --root "$tmp" >/dev/null 2>&1; then
  echo 'FAIL JSON doctor returned success for an uninstalled root'
  exit 1
fi
"$repo_dir/scripts/hades" doctor --json --root "$tmp" >"$tmp/doctor.json" 2>/dev/null || true
python3 - "$tmp/doctor.json" <<'PY'
import json, sys
value = json.load(open(sys.argv[1]))
assert value["status"] == "not-installed"
assert value["checks"]["source_manifest"] is True
print("PASS JSON doctor reports not-installed with a failing exit status")
PY
