"""Read-only MCP composition adapter for approved homelab endpoints."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from reconcile import summarize


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TOKEN_BYTES = 8192
TIMEOUT_SECONDS = 10
TOOLS = [Tool(
    name="homelab_summary",
    description=(
        "Read approved Proxmox runtime, NetBox intended inventory, and Uptime "
        "Kuma observed availability. Explain conflicts and stale observations; "
        "never perform writes or execute network commands."
    ),
    inputSchema={"type": "object", "properties": {}},
)]


def _read_token(path: str) -> str:
    token_path = Path(path)
    if not token_path.is_file() or token_path.is_symlink():
        raise ValueError("homelab token file must be a regular non-symlink file")
    mode = token_path.stat().st_mode & 0o777
    if mode not in {0o600, 0o640}:
        raise ValueError("homelab token file must be mode 0600 or 0640")
    token = token_path.read_bytes()
    if not token or len(token) > MAX_TOKEN_BYTES:
        raise ValueError("homelab token file is empty or exceeds the bounded size")
    return token.decode("utf-8").strip()


def _fetch(url: str, token_file: str = "") -> dict:
    if not url:
        raise ValueError("homelab source is not configured")
    if not url.startswith(("http://", "https://")):
        raise ValueError("homelab source must use HTTP(S)")
    headers = {"Accept": "application/json"}
    if token_file:
        headers["Authorization"] = f"Bearer {_read_token(token_file)}"
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("homelab response exceeds bounded size")
    result = json.loads(body)
    if not isinstance(result, dict):
        raise ValueError("homelab response must be a JSON object")
    return result


def homelab_summary() -> dict:
    values: list[dict | None] = []
    errors: list[str] = []
    specs = (
        (os.environ.get("HADES_PROXMOX_RESOURCES_URL", ""), os.environ.get("HADES_PROXMOX_TOKEN_FILE", "")),
        (os.environ.get("HADES_NETBOX_DEVICES_URL", ""), os.environ.get("HADES_NETBOX_TOKEN_FILE", "")),
        (os.environ.get("HADES_KUMA_STATUS_URL", ""), os.environ.get("HADES_KUMA_TOKEN_FILE", "")),
    )
    for url, token_file in specs:
        try:
            values.append(_fetch(url, token_file))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            values.append(None)
            errors.append(str(exc))
    result = summarize(*values)
    if errors:
        result["errors"] = errors
    return result


async def list_tools(_ctx, _params):
    return ListToolsResult(tools=TOOLS)


async def call_tool(_ctx, params):
    if params.name != "homelab_summary":
        raise ValueError(f"unknown tool: {params.name}")
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(homelab_summary(), sort_keys=True))])


async def main():
    server = Server("hades-homelab-readonly", on_list_tools=list_tools, on_call_tool=call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
