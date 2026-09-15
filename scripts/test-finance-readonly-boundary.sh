#!/usr/bin/env bash
set -euo pipefail

# Synthetic MCP-level finance boundary; no Actual server or credentials.
python3 - <<'PY'
import asyncio
import importlib.util
import sys
import types
from pathlib import Path

client_source = Path("integrations/actual-finance-readonly/actual_client.js").read_text()
assert "lstatSync" in client_source and "isSymbolicLink" in client_source
assert "MAX_SECRET_BYTES" in client_source and "mode !== 0o600" in client_source
assert "An explicit Actual Budget selection is required." in client_source

anyio = types.ModuleType("anyio")
anyio.run = lambda fn: None
sys.modules["anyio"] = anyio

class Server:
    def __init__(self, *args, **kwargs): pass
    def list_tools(self, *args, **kwargs): return lambda fn: fn
    def call_tool(self, *args, **kwargs): return lambda fn: fn
class Value:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)
mcp_lowlevel = types.ModuleType("mcp.server.lowlevel")
mcp_lowlevel.Server = Server
mcp_stdio = types.ModuleType("mcp.server.stdio")
mcp_stdio.stdio_server = object
mcp_types = types.ModuleType("mcp.types")
for name in ("CallToolResult", "ListToolsResult", "TextContent", "Tool"):
    setattr(mcp_types, name, Value)
sys.modules.update({"mcp": types.ModuleType("mcp"), "mcp.server": types.ModuleType("mcp.server"),
                    "mcp.server.lowlevel": mcp_lowlevel, "mcp.server.stdio": mcp_stdio,
                    "mcp.types": mcp_types})

spec = importlib.util.spec_from_file_location("finance_server", Path("integrations/actual-finance-readonly/server.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

async def check():
    listed = await module.list_tools(None, None)
    names = [tool.name for tool in listed.tools]
    assert names == ["finance_accounts", "finance_transactions", "finance_status"], names
    original_transactions = module.finance_transactions
    calls = []
    module.finance_accounts = lambda: calls.append("accounts") or {"ok": True}
    module.finance_status = lambda: calls.append("status") or {"ok": True}
    module.finance_transactions = lambda *args: calls.append("transactions") or {"ok": True}
    for name in names:
        result = await module.call_tool(None, Value(name=name, arguments={}))
        assert result.content[0].type == "text"
    assert calls == ["accounts", "transactions", "status"], calls
    try:
        await module.call_tool(None, Value(name="finance_write", arguments={}))
    except ValueError:
        pass
    else:
        raise AssertionError("unknown finance tool was accepted")
    module.finance_transactions = original_transactions
    module._call = lambda *args, **kwargs: {"ok": True}
    assert module.finance_transactions("2026-09-14", "2026-09-13")["ok"] is False
    assert module.finance_transactions("bad", "2026-09-14")["ok"] is False
    assert module.finance_transactions("2026-09-13", "2026-09-14", limit="bad")["ok"] is False

asyncio.run(check())
print("PASS finance read-only MCP boundary")
print("PASS Actual password and budget selection boundaries fail closed")
PY
