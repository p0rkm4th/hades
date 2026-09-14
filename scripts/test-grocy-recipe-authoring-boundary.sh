#!/usr/bin/env bash
set -euo pipefail

# Validate the serving-count adapter without contacting Grocy or loading
# optional MCP dependencies. Live canonical acceptance is operator-only.
python - <<'PY'
import asyncio
import importlib.util
import os
import sys
import types
from pathlib import Path

os.environ["GROCY_API_KEY"] = "synthetic-test-key"

anyio = types.ModuleType("anyio")
anyio.run = lambda fn: None
sys.modules["anyio"] = anyio

class Server:
    def __init__(self, *_args, **_kwargs): pass
    def list_tools(self): return lambda fn: fn
    def call_tool(self, **_kwargs): return lambda fn: fn

class Tool:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)
class ListToolsResult:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)
class CallToolResult:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)
class TextContent:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)

mcp_server = types.ModuleType("mcp.server")
mcp_lowlevel = types.ModuleType("mcp.server.lowlevel")
mcp_lowlevel.Server = Server
mcp_stdio = types.ModuleType("mcp.server.stdio")
async def stdio_server(): raise AssertionError("stdio must not run in boundary test")
mcp_stdio.stdio_server = stdio_server
mcp_types = types.ModuleType("mcp.types")
mcp_types.Tool = Tool
mcp_types.ListToolsResult = ListToolsResult
mcp_types.CallToolResult = CallToolResult
mcp_types.TextContent = TextContent
sys.modules.update({
    "mcp": types.ModuleType("mcp"), "mcp.server": mcp_server,
    "mcp.server.lowlevel": mcp_lowlevel,
    "mcp.server.stdio": mcp_stdio, "mcp.types": mcp_types,
})

httpx = types.ModuleType("httpx")
class TimeoutException(Exception): pass
class HTTPError(Exception): pass
httpx.TimeoutException = TimeoutException
httpx.HTTPError = HTTPError
httpx.AsyncClient = object
sys.modules["httpx"] = httpx

source_path = Path("integrations/grocy-recipe-authoring/server.py")
spec = importlib.util.spec_from_file_location("hades_grocy_recipe_authoring", source_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

async def check():
    cases = [("", 1), ("Recipe", 0), ("Recipe", 1001), ("Recipe", "two")]
    for recipe, servings in cases:
        result = await module.set_servings(recipe, servings)
        assert result["outcome"] == "FAILED", (recipe, servings, result)

asyncio.run(check())
assert module.TOOL_NAME == "recipe_set_servings"
assert "base_servings" in source_path.read_text()
print("PASS Grocy recipe-authoring validation boundary")
PY
