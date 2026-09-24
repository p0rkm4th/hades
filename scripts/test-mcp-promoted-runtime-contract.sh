#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python3 - "$repo_dir" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
paths = [
    root / "integrations/recipe-ingest/server.py",
    root / "integrations/actual-finance-import/server.py",
    root / "integrations/grocy-recipe-authoring/server.py",
    root / "integrations/agent-zero-mcp/server.py",
    root / "integrations/homelab-readonly/server.py",
]
for path in paths:
    text = path.read_text(encoding="utf-8")
    if "server.list_tools()(" in text or "server.call_tool()(" in text:
        raise SystemExit(f"FAIL {path} still uses the removed decorator API")
    if "on_list_tools=" not in text or "on_call_tool=" not in text:
        raise SystemExit(f"FAIL {path} is not wired to the promoted Hermes callback API")
if "ListToolsResult(tools=TOOLS)" not in (root / "integrations/homelab-readonly/server.py").read_text(encoding="utf-8"):
    raise SystemExit("FAIL homelab adapter does not return a typed list-tools result")
print("PASS HADES MCP adapters target the promoted Hermes runtime API")
PY
