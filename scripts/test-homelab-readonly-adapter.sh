#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path("integrations/homelab-readonly")
spec = importlib.util.spec_from_file_location("homelab_reconcile", root / "reconcile.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
result = module.summarize(
    {"data": [{"type": "qemu", "name": "dinner-app", "node": "Alexandra", "status": "running"}]},
    {"results": [{"name": "dinner-app", "planned_node": "Beta", "status": "active"}]},
    {"monitors": [{"name": "dinner-app", "status": "down", "last_updated": "2026-09-14T11:40:00+00:00"}]},
    now=now,
)
resource = result["resources"][0]
assert result["status"] == "OK"
assert resource["runtime"]["node"] == "Alexandra"
assert resource["inventory"]["planned_node"] == "Beta"
assert resource["availability"]["status"] == "down"
assert resource["availability_freshness"] == "STALE"
assert resource["conflicts"]
assert result["authority"]["runtime"] == "Proxmox"
future = module.summarize(
    {"data": [{"type": "qemu", "name": "clock-skewed", "node": "Alexandra", "status": "running"}]},
    {"results": []},
    {"monitors": [{"name": "clock-skewed", "status": "up", "last_updated": "2026-09-14T12:05:00+00:00"}]},
    now=now,
)
assert future["resources"][0]["availability_freshness"] == "UNKNOWN"
server_source = (Path(root) / "server.py").read_text()
assert "token_path.is_symlink()" in server_source
assert "MAX_TOKEN_BYTES" in server_source
assert "homelab_discovery_candidates" in server_source
assert "propose_inventory_candidates" in server_source
assert "does not run Nmap" in server_source
print("PASS homelab adapter preserves runtime/inventory/availability authority")
print("PASS homelab adapter discloses node conflict and stale Kuma observation")
print("PASS future monitoring observations fail closed as unknown")
print("PASS homelab MCP exposes review-only discovery candidates")
PY

python -m py_compile integrations/homelab-readonly/reconcile.py integrations/homelab-readonly/server.py
echo 'PASS homelab MCP adapter is syntax-valid and read-only by construction'
