#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import importlib.util
import os
import sys
import tempfile
import types
from pathlib import Path

secret_dir = Path(tempfile.mkdtemp(prefix="hades-recipe-secret-test-"))
os.environ["HADES_GROCY_API_KEY_FILE"] = str(secret_dir / "recipe-key")
fake_recipe = types.ModuleType("recipe_ingest")
fake_recipe.GrocyRecipeImporter = object
fake_recipe.GrocyRequestError = ValueError
fake_recipe.extract_from_paste = lambda *args: {}
fake_recipe.extract_from_url = lambda *args: {}
sys.modules["recipe_ingest"] = fake_recipe
sys.modules["anyio"] = types.ModuleType("anyio")
mcp = types.ModuleType("mcp")
mcp_server = types.ModuleType("mcp.server")
mcp_low = types.ModuleType("mcp.server.lowlevel")
mcp_low.Server = object
mcp_stdio = types.ModuleType("mcp.server.stdio")
mcp_stdio.stdio_server = object
mcp_types = types.ModuleType("mcp.types")
for name in ("CallToolResult", "ListToolsResult", "TextContent", "Tool"):
    setattr(mcp_types, name, object)
sys.modules.update({"mcp": mcp, "mcp.server": mcp_server, "mcp.server.lowlevel": mcp_low, "mcp.server.stdio": mcp_stdio, "mcp.types": mcp_types})

spec = importlib.util.spec_from_file_location("recipe_server", "integrations/recipe-ingest/server.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
key = Path(os.environ["HADES_GROCY_API_KEY_FILE"])

def expect_failure(path, mode=None, content=b"key"):
    if path.exists() or path.is_symlink():
        path.unlink()
    if mode is None:
        path.write_bytes(content)
    else:
        path.write_bytes(content)
        path.chmod(mode)
    try:
        module._api_key()
    except (ValueError, UnicodeError):
        return
    raise AssertionError(f"unsafe recipe secret accepted: {path} {mode}")

key.write_bytes(b"synthetic-key\n")
key.chmod(0o600)
assert module._api_key() == "synthetic-key"
expect_failure(key, 0o644)
expect_failure(key, 0o600, b"")
expect_failure(key, 0o600, b"x" * (module.MAX_API_KEY_BYTES + 1))
target = Path(tempfile.mkdtemp()) / "target"
target.write_text("synthetic-key")
target.chmod(0o600)
link = key
if link.exists() or link.is_symlink():
    link.unlink()
link.symlink_to(target)
try:
    module._api_key()
except ValueError:
    pass
else:
    raise AssertionError("symlinked recipe secret accepted")
link.unlink()
target.unlink()
target.parent.rmdir()
secret_dir.rmdir()
print("PASS recipe Grocy API key requires bounded regular file and safe permissions")
PY
