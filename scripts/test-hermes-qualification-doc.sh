#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

source = Path("docs/hermes-staging-evaluation.md").read_text(encoding="utf-8")
if "## HADES qualification suite definition" not in source:
    raise SystemExit("HADES qualification suite definition is missing")
if "Production remains on Hermes 0.14.0" not in source:
    raise SystemExit("production baseline is not explicit")
start = source.index("| Candidate failure | Classification | Disposition |")
end = source.index("\n\nOptional-provider failures", start)
rows = []
for line in source[start:end].splitlines()[2:]:
    if not line.startswith("|"):
        continue
    cells = [cell.strip() for cell in line.strip("|").split("|")]
    if len(cells) != 3:
        raise SystemExit(f"malformed candidate classification row: {line}")
    rows.append(cells)
if len(rows) != 5:
    raise SystemExit(f"expected five residual candidate rows, found {len(rows)}")
allowed = {"HADES PRODUCTION RELEVANT", "UPSTREAM DEFECT", "OPTIONAL PROVIDER",
           "HOST-SENSITIVE", "UPDATE-SHIM ONLY", "BROWSER-ENVIRONMENT ONLY"}
for failure, classification, disposition in rows:
    if classification not in allowed:
        raise SystemExit(f"invalid single classification for {failure}: {classification}")
    if not disposition:
        raise SystemExit(f"missing disposition for {failure}")
print("PASS Hermes qualification classifications are explicit and singular")
PY
