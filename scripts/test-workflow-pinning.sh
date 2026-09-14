#!/usr/bin/env bash
set -euo pipefail

# Keep GitHub Actions dependencies immutable. Version comments may document a
# release, but execution must resolve to a full commit SHA.

workflow_root=${1:-.github/workflows}
[[ -d "$workflow_root" ]] || {
  printf 'FAIL workflow directory missing: %s\n' "$workflow_root" >&2
  exit 1
}

python3 - "$workflow_root" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
references = []
for path in sorted(root.rglob("*")):
    if path.suffix not in {".yml", ".yaml"}:
        continue
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.search(r"\buses:\s*([^\s#]+)", line)
        if match:
            references.append(match.group(1))

if not references:
    raise SystemExit("FAIL no workflow action references found")
for reference in references:
    ref = reference.rsplit("@", 1)[-1]
    if not re.fullmatch(r"[0-9a-fA-F]{40}", ref):
        raise SystemExit(f"FAIL mutable workflow action reference: {reference}")
print(f"PASS workflow action references pinned: {len(references)}")
PY
