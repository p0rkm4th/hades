#!/usr/bin/env bash
set -euo pipefail

# Secret-free regression coverage for the bounded Agent Zero MCP adapter.
# Stub optional runtime dependencies so this runs in public CI.
python - <<'PY'
import asyncio
import importlib.util
import os
import sys
import types
from pathlib import Path

os.environ["AGENT_ZERO_API_KEY"] = "synthetic-test-key"
os.environ["AGENT_ZERO_MAX_TASK_CHARS"] = "8"
os.environ["AGENT_ZERO_MAX_RESPONSE_CHARS"] = "10"
os.environ["AGENT_ZERO_MAX_CONTEXT_ID_CHARS"] = "4"

class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload

class AsyncClient:
    payload = {"response": "bounded", "context_id": "ctx"}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, *args, **kwargs):
        return Response(self.payload)

httpx = types.ModuleType("httpx")
httpx.AsyncClient = AsyncClient
httpx.HTTPError = type("HTTPError", (Exception,), {})
sys.modules["httpx"] = httpx
sys.modules["anyio"] = types.ModuleType("anyio")

mcp = types.ModuleType("mcp")
mcp_server = types.ModuleType("mcp.server")
mcp_lowlevel = types.ModuleType("mcp.server.lowlevel")
mcp_lowlevel.Server = object
mcp_stdio = types.ModuleType("mcp.server.stdio")
mcp_stdio.stdio_server = object
mcp_types = types.ModuleType("mcp.types")
for name in ("CallToolResult", "ListToolsResult", "TextContent", "Tool"):
    setattr(mcp_types, name, object)
sys.modules.update({
    "mcp": mcp,
    "mcp.server": mcp_server,
    "mcp.server.lowlevel": mcp_lowlevel,
    "mcp.server.stdio": mcp_stdio,
    "mcp.types": mcp_types,
})

spec = importlib.util.spec_from_file_location(
    "agent_zero_server", Path("integrations/agent-zero-mcp/server.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

async def main():
    assert not (await module._delegate("123456789"))["ok"]
    assert not (await module._delegate("task", "12345"))["ok"]
    AsyncClient.payload = {"response": "01234567890", "context_id": "ctx"}
    assert not (await module._delegate("task"))["ok"]
    AsyncClient.payload = {"response": "bounded", "context_id": "ctx"}
    result = await module._delegate("task", "1234")
    assert result == {"ok": True, "context_id": "ctx", "response": "bounded"}

asyncio.run(main())
print("PASS Agent Zero input/output bounds")
PY
