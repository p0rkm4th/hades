#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

profile = Path("hermes/config.yaml.example").read_text(encoding="utf-8")
env = Path("hermes/env.example").read_text(encoding="utf-8")
for marker in (
    "homelab-readonly:",
    "integrations/homelab-readonly/server.py",
    'HADES_PROXMOX_TOKEN_FILE',
    'HADES_NETBOX_TOKEN_FILE',
    'HADES_KUMA_TOKEN_FILE',
    'HADES_CAPABILITY_MATRIX_FILE',
    'HADES_DISCOVERY_ALLOWED_NETWORKS',
):
    if marker not in profile and marker not in env:
        raise SystemExit(f"FAIL homelab MCP registration missing {marker}")
if "HADES_PROXMOX_TOKEN_SECRET" in profile or "HADES_NETBOX_TOKEN=\"" in profile:
    raise SystemExit("FAIL homelab profile embeds raw token inputs")
if "integrations/homelab-readonly/server.py" not in profile:
    raise SystemExit("FAIL homelab adapter is not registered in the Hermes profile")
print("PASS homelab read-only MCP is registered with protected token-file inputs")
PY
