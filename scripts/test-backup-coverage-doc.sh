#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

source = Path("docs/backup-restore.md").read_text(encoding="utf-8")
required = (
    "LLDAP", "Open WebUI", "Hindsight", "Grocy", "Actual Budget",
    "Hermes", "Agent Zero", "SearXNG", "HADES private configuration",
)
matrix_start = source.index("| Component | Authority / reconstructability |")
matrix_end = source.index("### Recovery objectives", matrix_start)
matrix = source[matrix_start:matrix_end]
for component in required:
    rows = [line for line in matrix.splitlines() if line.startswith(f"| {component} |")]
    if len(rows) != 1:
        raise SystemExit(f"backup coverage row missing or duplicated: {component}")
if "### Recovery objectives" not in source:
    raise SystemExit("recovery objectives section is missing")
start = source.index("| Component | RPO assumption | RTO assumption |")
end = source.index("## Live deployment mount inventory", start)
rows = [line for line in source[start:end].splitlines()[2:] if line.startswith("|")]
if len(rows) != len(required):
    raise SystemExit(f"expected {len(required)} recovery objective rows, found {len(rows)}")
for row in rows:
    cells = [cell.strip() for cell in row.strip("|").split("|")]
    if len(cells) != 3 or not cells[1] or not cells[2]:
        raise SystemExit(f"incomplete recovery objective row: {row}")
print("PASS backup coverage includes every persistent component and RPO/RTO assumptions")
PY
