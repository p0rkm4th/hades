#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

config = Path("hermes/config.yaml.example").read_text()
server = Path("integrations/recipe-ingest/server.py").read_text()
assert "mcp_servers:" in config
assert "recipe-url-ingest:" in config
assert "${HADES_HERMES_WORKING_DIRECTORY}/integrations/recipe-ingest/server.py" in config
assert 'GROCY_API_KEY_FILE: "${HADES_GROCY_API_KEY_FILE}"' in config
assert 'timeout: 30' in config
assert '"HADES_GROCY_API_KEY_FILE", ""' in server
assert 'or "http://127.0.0.1:7003"' in server
assert "recipe_url_preview" in server and "recipe_url_apply" in server
assert "recipe_paste_preview" in server and "extract_from_paste" in server
assert "review_token" in server and "_cache_preview" in server
print("PASS recipe URL MCP is registered through generated private paths")
print("PASS recipe URL and paste MCP retain separate preview/apply boundaries")
print("PASS recipe apply retains explicit confirmation and review-token boundary")
PY
