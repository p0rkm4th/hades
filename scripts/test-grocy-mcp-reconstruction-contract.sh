#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-grocy-mcp-contract.XXXXXX")
chmod 700 "$work"
trap 'rm -rf -- "$work"' EXIT

python3 - "$repo_dir" <<'PY'
import pathlib, sys, yaml
root = pathlib.Path(sys.argv[1])
versions = {}
for line in (root / "config/versions.env").read_text().splitlines():
    if line and not line.startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        versions[key] = value
lock = (root / "integrations/grocy-mcp/requirements.lock").read_text().splitlines()
assert f"grocy-mcp=={versions['HADES_GROCY_MCP_VERSION']}" in lock
assert all(line and "==" in line and "#" not in line for line in lock), "lock must contain exact package versions"
config = yaml.safe_load((root / "hermes/config.yaml.example").read_text())
grocy = config["mcp_servers"]["grocy"]
assert grocy["command"] == "python3"
assert grocy["args"] == ["${HADES_HERMES_WORKING_DIRECTORY}/integrations/grocy-mcp/launch.py"]
assert grocy["env"] == {
    "GROCY_URL": "${HADES_GROCY_URL}",
    "GROCY_API_KEY_FILE": "${HADES_GROCY_API_KEY_FILE}",
}
expected = {
    "stock_overview_tool", "stock_product_info_tool", "stock_consume_tool",
    "shopping_list_view_tool", "shopping_list_add_tool", "shopping_list_remove_tool",
    "workflow_match_products_preview_tool", "workflow_stock_intake_preview_tool",
    "workflow_stock_intake_apply_tool", "recipe_fulfillment_tool",
    "recipe_add_to_shopping_tool", "recipes_list_tool", "recipe_details_tool",
    "recipe_create_by_name_tool", "recipe_update_tool", "recipe_add_ingredient_tool",
    "recipe_remove_ingredient_tool",
}
assert set(grocy["tools"]["include"]) == expected
readiness = (root / "scripts/check-grocy-mcp-runtime.py").read_text()
assert 'client.call_tool("stock_overview_tool", {}, raise_on_error=False)' in readiness
assert "if stock.is_error" in readiness
installer = (root / "scripts/install-hades.sh").read_text()
assert "REQUIRED_|SYNTHETIC_GROCY_API_KEY" in installer
bootstrap = (root / "scripts/bootstrap-grocy.sh").read_text()
assert "deploy/grocy.compose.yaml" in bootstrap
assert "hades-grocy-net" in bootstrap
assert "docker compose" in bootstrap
assert "HADES_GROCY_IMAGE" in bootstrap and '"127.0.0.1"' in bootstrap
assert "docker volume rm" not in bootstrap and "compose down --volumes" not in bootstrap
print("PASS reconstruction pins and scopes the maintained Grocy MCP in the generated Hermes profile")
PY

python3 - "$repo_dir/integrations/grocy-mcp/launch.py" "$work" <<'PY'
import contextlib, importlib.util, io, os, pathlib, sys
from unittest.mock import patch
launcher, root = sys.argv[1], pathlib.Path(sys.argv[2])
secret = root / "key"
secret.write_text("synthetic-grocy-secret\n")
secret.chmod(0o600)
spec = importlib.util.spec_from_file_location("hades_grocy_launcher", launcher)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
child = root / "mcp-child"
child.write_text("#!/bin/sh\nexit 0\n")
child.chmod(0o700)
module.MCP_EXECUTABLE = str(child)
base = {"GROCY_URL": "http://127.0.0.1:7003", "GROCY_API_KEY_FILE": str(secret)}
with contextlib.ExitStack() as stack:
    stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
    stack.enter_context(patch.dict(os.environ, base, clear=False))
    execve = stack.enter_context(patch.object(module.os, "execve", side_effect=SystemExit(0)))
    try:
        module.main()
    except SystemExit as exc:
        assert exc.code == 0
call = execve.call_args
assert call.args[0] == str(child)
assert call.args[1] == [str(child), "--transport=stdio"]
assert call.args[2]["GROCY_API_KEY"] == "synthetic-grocy-secret"
assert "GROCY_API_KEY_FILE" not in call.args[2]

secret.chmod(0o644)
errors = io.StringIO()
with contextlib.redirect_stderr(errors), patch.dict(os.environ, base, clear=False):
    try:
        module.main()
    except SystemExit as exc:
        assert exc.code == 2
assert "mode 0600 or 0640" in errors.getvalue()
secret.chmod(0o600)
base["GROCY_URL"] = "http://user:password@127.0.0.1:7003"
errors = io.StringIO()
with contextlib.redirect_stderr(errors), patch.dict(os.environ, base, clear=False):
    try:
        module.main()
    except SystemExit as exc:
        assert exc.code == 2
assert "without embedded credentials" in errors.getvalue()
assert "synthetic-grocy-secret" not in errors.getvalue()
print("PASS Grocy launcher protects the key file, rejects unsafe inputs, and keeps the key out of diagnostics")
PY
