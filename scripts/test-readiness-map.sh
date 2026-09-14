#!/usr/bin/env bash
set -euo pipefail

# Keep the stable-v1 readiness table complete, unique, and actionable.
python3 - <<'PY'
from pathlib import Path

source = Path("docs/stable-v1-readiness.md").read_text(encoding="utf-8")
start = source.index("## Stable-v1 readiness score")
end = source.index("## Source-of-truth adversarial contract", start)
rows = []
for line in source[start:end].splitlines():
    if line.startswith("| ") and line.count("|") == 4 and not line.startswith("| Capability"):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 3:
            rows.append(cells)

required = (
    "Owner daily-driver", "Household multi-user", "Private memory",
    "Shared household state", "Web/search", "Bounded operator", "Finance",
    "Homelab", "Home Assistant", "Automation", "Recovery",
    "Installation/rebuild", "Security", "Performance",
)
names = [row[0] for row in rows]
if names != list(required):
    raise SystemExit(f"readiness capabilities/order mismatch: {names}")
allowed = {"PASS", "PARTIAL", "OWNER-GATED", "DEFERRED"}
for capability, status, contract in rows:
    if status not in allowed:
        raise SystemExit(f"invalid readiness status for {capability}: {status}")
    if not contract or contract.lower() in {"tbd", "unknown", "n/a"}:
        raise SystemExit(f"missing smallest remaining contract for {capability}")
print(f"PASS stable-v1 readiness map: {len(rows)} capabilities")
PY
