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
    error = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, *args, **kwargs):
        if self.error:
            raise self.error
        return Response(self.payload)

httpx = types.ModuleType("httpx")
httpx.AsyncClient = AsyncClient
httpx.HTTPError = type("HTTPError", (Exception,), {})
httpx.TimeoutException = type("TimeoutException", (httpx.HTTPError,), {})
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
    module.MAX_TASK_CHARS = 100
    wrong_task_type = await module._delegate({"task": "inspect"})
    assert not wrong_task_type["ok"] and wrong_task_type["outcome"] == "FAILED"
    wrong_context_type = await module._delegate("task", {"id": "ctx"})
    assert not wrong_context_type["ok"] and wrong_context_type["outcome"] == "FAILED"
    unsafe = await module._delegate("password")
    assert not unsafe["ok"] and unsafe["outcome"] == "FAILED"
    unsafe_socket = await module._delegate("/var/run/docker.sock")
    assert not unsafe_socket["ok"] and unsafe_socket["outcome"] == "FAILED"
    for unsafe_task in ("reboot the host", "deploy the service", "install a package", "run a command", "network scan 192.0.2.0/24", "nmap the subnet", "chmod the file"):
        unsafe = await module._delegate(unsafe_task)
        assert not unsafe["ok"] and unsafe["outcome"] == "FAILED", unsafe_task
    AsyncClient.payload = {"response": "01234567890", "context_id": "ctx"}
    oversized = await module._delegate("task")
    assert not oversized["ok"] and oversized["outcome"] == "OUTCOME UNKNOWN"
    AsyncClient.payload = {"response": "bounded", "context_id": "12345"}
    oversized_context = await module._delegate("task")
    assert not oversized_context["ok"] and oversized_context["outcome"] == "OUTCOME UNKNOWN"
    AsyncClient.payload = {"response": "bounded", "context_id": 1234}
    malformed_context = await module._delegate("task")
    assert not malformed_context["ok"] and malformed_context["outcome"] == "OUTCOME UNKNOWN"
    AsyncClient.error = module.httpx.TimeoutException()
    timed_out = await module._delegate("task")
    assert not timed_out["ok"] and timed_out["outcome"] == "OUTCOME UNKNOWN"
    AsyncClient.error = module.httpx.HTTPError("synthetic HTTP status failure")
    http_failed = await module._delegate("task")
    assert not http_failed["ok"] and http_failed["outcome"] == "OUTCOME UNKNOWN"
    class ResponseError(module.httpx.HTTPError):
        response = types.SimpleNamespace(status_code=400)
    AsyncClient.error = ResponseError("synthetic definitive rejection")
    rejected = await module._delegate("task")
    assert not rejected["ok"] and rejected["outcome"] == "FAILED"
    module.httpx.ConnectError = type("ConnectError", (module.httpx.HTTPError,), {})
    AsyncClient.error = module.httpx.ConnectError("synthetic pre-request connection failure")
    connect_failed = await module._delegate("task")
    assert not connect_failed["ok"] and connect_failed["outcome"] == "FAILED"
    AsyncClient.error = ValueError("synthetic malformed JSON")
    malformed = await module._delegate("task")
    assert not malformed["ok"] and malformed["outcome"] == "OUTCOME UNKNOWN"
    AsyncClient.error = None
    AsyncClient.payload = {"response": "bounded", "context_id": "ctx"}
    result = await module._delegate("task", "1234")
    assert result == {"ok": True, "outcome": "SUCCEEDED", "context_id": "ctx", "response": "bounded"}
    status_result = await module._delegate("update me on service status")
    assert status_result["outcome"] == "SUCCEEDED", status_result

asyncio.run(main())
print("PASS Agent Zero input/output bounds")
PY
