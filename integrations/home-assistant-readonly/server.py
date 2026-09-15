"""Bounded, read-only Home Assistant REST MCP adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from policy import shape_state, validate_allowlist

MAX_RESPONSE_BYTES = 512 * 1024
TIMEOUT_SECONDS = 10
TOOLS = [
    Tool(name="home_assistant_read", description="Read one explicitly allowlisted, non-sensitive Home Assistant entity. Read-only.", inputSchema={"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"]}),
    Tool(name="home_assistant_selected_states", description="Read all explicitly selected, non-sensitive Home Assistant entities. Read-only.", inputSchema={"type": "object", "properties": {}}),
]


def _allowlist() -> list[str]:
    return validate_allowlist(os.environ.get("HADES_HOME_ASSISTANT_ENTITY_ALLOWLIST", "").split(","))


def _fetch(entity_id: str) -> dict:
    selected = _allowlist()
    if entity_id not in selected:
        raise ValueError("entity is not in the approved Home Assistant allowlist")
    base = os.environ.get("HADES_HOME_ASSISTANT_URL", "").rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise ValueError("Home Assistant URL is not configured")
    headers = {"Accept": "application/json"}
    token_file = os.environ.get("HADES_HOME_ASSISTANT_TOKEN_FILE", "")
    if token_file:
        headers["Authorization"] = f"Bearer {Path(token_file).read_text(encoding='utf-8').strip()}"
    request = Request(f"{base}/api/states/{quote(entity_id, safe='.')}", headers=headers, method="GET")
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("Home Assistant response exceeds bounded size")
    result = json.loads(body)
    if not isinstance(result, dict):
        raise ValueError("Home Assistant response must be a JSON object")
    return result


def read_entity(entity_id: str) -> dict:
    try:
        state = _fetch(entity_id)
        return {"status": "OK", "result": shape_state(state)}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"status": "FAILED", "entity_id": entity_id, "error": str(exc)}


def read_selected() -> dict:
    try:
        selected = _allowlist()
    except ValueError as exc:
        return {"status": "FAILED", "error": str(exc)}
    results = [read_entity(entity_id) for entity_id in selected]
    return {"status": "OK" if all(item["status"] == "OK" for item in results) else "PARTIAL", "results": results}


async def list_tools(_ctx, _params):
    return ListToolsResult(tools=TOOLS)


async def call_tool(_ctx, params):
    if params.name == "home_assistant_read":
        result = read_entity(str(params.arguments.get("entity_id", "")))
    elif params.name == "home_assistant_selected_states":
        result = read_selected()
    else:
        raise ValueError(f"unknown tool: {params.name}")
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, sort_keys=True))])


async def main():
    server = Server("hades-home-assistant-readonly", on_list_tools=list_tools, on_call_tool=call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
