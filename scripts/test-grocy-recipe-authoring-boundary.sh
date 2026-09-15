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
class Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPError("synthetic HTTP failure")
    def json(self):
        return self._payload
class Client:
    def __init__(self, *args, **kwargs):
        self.calls = []
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None
    async def get(self, url):
        self.calls.append(("GET", url))
        if url.endswith("/recipes"):
            return Response([{"id": 7, "name": "Recipe", "base_servings": 1}])
        return Response({"id": 7, "name": "Recipe", "base_servings": 2})
    async def put(self, url, json):
        self.calls.append(("PUT", url, json))
        return Response({"id": 7, "base_servings": json["base_servings"]})
httpx.AsyncClient = Client
sys.modules["httpx"] = httpx

source_path = Path("integrations/grocy-recipe-authoring/server.py")
spec = importlib.util.spec_from_file_location("hades_grocy_recipe_authoring", source_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

async def check():
    cases = [
        ("", 1), ("Recipe", 0), ("Recipe", 1001), ("Recipe", "two"),
        ("Recipe", 2.5), ("Recipe", True), ("Recipe", "2"),
    ]
    for recipe, servings in cases:
        result = await module.set_servings(recipe, servings)
        assert result["outcome"] == "FAILED", (recipe, servings, result)
    result = await module.set_servings("Recipe", 2)
    assert result == {"ok": True, "outcome": "SUCCEEDED", "recipe_id": 7, "base_servings": 2}
    duplicate = await module.set_servings("Recipe", 2)
    assert duplicate == result, duplicate

    # Re-import the stateless adapter to model an immediate restart. It must
    # resolve and verify canonical state again rather than relying on memory.
    restarted_spec = importlib.util.spec_from_file_location(
        "hades_grocy_recipe_authoring_restart", source_path
    )
    restarted = importlib.util.module_from_spec(restarted_spec)
    restarted_spec.loader.exec_module(restarted)
    restarted_result = await restarted.set_servings("Recipe", 2)
    assert restarted_result == result, restarted_result

    class MissingRecipeClient(Client):
        async def get(self, url):
            if url.endswith("/recipes"):
                return Response([])
            return Response({"id": 7, "base_servings": 1})
    module.httpx.AsyncClient = MissingRecipeClient
    result = await module.set_servings("Missing", 2)
    assert result["outcome"] == "FAILED", result

    class DuplicateRecipeClient(Client):
        async def get(self, url):
            if url.endswith("/recipes"):
                return Response([
                    {"id": 7, "name": "Recipe"},
                    {"id": 8, "name": "Recipe"},
                ])
            return Response({"id": 7, "base_servings": 1})
    module.httpx.AsyncClient = DuplicateRecipeClient
    result = await module.set_servings("Recipe", 2)
    assert result["outcome"] == "FAILED", result

    class MalformedRecipeListClient(Client):
        async def get(self, url):
            if url.endswith("/recipes"):
                return Response({"recipes": "not-a-list"})
            return Response({"id": 7, "base_servings": 1})
    module.httpx.AsyncClient = MalformedRecipeListClient
    result = await module.set_servings("Recipe", 2)
    assert result["outcome"] == "FAILED", result

    class TimeoutClient(Client):
        async def get(self, url): raise TimeoutException("synthetic timeout")
    module.httpx.AsyncClient = TimeoutClient
    result = await module.set_servings("Recipe", 2)
    assert result["outcome"] == "FAILED", result

    class PostWriteTimeoutClient(Client):
        async def put(self, url, json): raise TimeoutException("synthetic post-write timeout")
    module.httpx.AsyncClient = PostWriteTimeoutClient
    result = await module.set_servings("Recipe", 2)
    assert result["outcome"] == "OUTCOME UNKNOWN", result

    class PreMutationHTTPClient(Client):
        async def get(self, url): raise HTTPError("synthetic resolution failure")
    module.httpx.AsyncClient = PreMutationHTTPClient
    result = await module.set_servings("Recipe", 2)
    assert result["outcome"] == "FAILED", result

    class ConnectError(HTTPError): pass
    module.httpx.ConnectError = ConnectError
    class PreWriteConnectClient(Client):
        async def put(self, url, json): raise ConnectError("synthetic connect failure")
    module.httpx.AsyncClient = PreWriteConnectClient
    result = await module.set_servings("Recipe", 2)
    assert result["outcome"] == "FAILED", result

    class HTTPVerificationClient(Client):
        async def get(self, url):
            if url.endswith("/recipes"):
                return Response([{"id": 7, "name": "Recipe", "base_servings": 1}])
            return Response({}, status_code=503)
    module.httpx.AsyncClient = HTTPVerificationClient
    result = await module.set_servings("Recipe", 2)
    assert result["outcome"] == "OUTCOME UNKNOWN", result

    class PostWriteConnectClient(Client):
        async def get(self, url):
            if url.endswith("/recipes"):
                return Response([{"id": 7, "name": "Recipe", "base_servings": 1}])
            raise ConnectError("synthetic verification connection failure")
    module.httpx.AsyncClient = PostWriteConnectClient
    result = await module.set_servings("Recipe", 2)
    assert result["outcome"] == "OUTCOME UNKNOWN", result

    class MalformedVerificationClient(Client):
        async def get(self, url):
            if url.endswith("/recipes"):
                return Response([{"id": 7, "name": "Recipe", "base_servings": 1}])
            return Response("not-an-object")
    module.httpx.AsyncClient = MalformedVerificationClient
    result = await module.set_servings("Recipe", 2)
    assert result["outcome"] == "OUTCOME UNKNOWN", result

    class CoercibleVerificationClient(Client):
        async def get(self, url):
            if url.endswith("/recipes"):
                return Response([{"id": 7, "name": "Recipe", "base_servings": 1}])
            return Response({"id": 7, "base_servings": True})
    module.httpx.AsyncClient = CoercibleVerificationClient
    result = await module.set_servings("Recipe", 1)
    assert result["outcome"] == "OUTCOME UNKNOWN", result

    listed = await module.list_tools()
    assert listed.tools[0].name == module.TOOL_NAME
    called = await module.call_tool(module.TOOL_NAME, {"recipe": "Recipe", "servings": 2})
    assert called.content[0].type == "text"

asyncio.run(check())
assert module.TOOL_NAME == "recipe_set_servings"
assert "base_servings" in source_path.read_text()
print("PASS Grocy recipe-authoring validation boundary")
PY
