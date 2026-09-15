"""Preview-only MCP surface for local Actual Budget file intake."""

from __future__ import annotations

import json
from typing import Any

import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from service import preview_apply_request, preview_file


TOOLS = [
    Tool(
        name="finance_file_preview",
        description=(
            "Preview a local CSV, QIF, OFX, QFX, or CAMT file for Actual Budget. "
            "The file is inline base64 only; this tool never uploads or writes. "
            "CSV requires explicit mapping_json."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_base64": {"type": "string", "description": "Inline base64 file bytes; no paths or URLs."},
                "filename": {"type": "string"},
                "mapping_json": {"type": "string", "description": "CSV column mapping JSON object."},
                "existing_transactions_json": {"type": "string", "description": "Optional canonical rows for duplicate analysis."},
            },
            "required": ["file_base64", "filename"],
        },
    ),
    Tool(
        name="finance_file_apply_preview",
        description=(
            "Build an explicit, confirmation-gated Actual importTransactions request "
            "from a CSV preview. This tool never executes the request."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "preview_json": {"type": "string"},
                "confirm": {"type": "boolean"},
            },
            "required": ["preview_json", "confirm"],
        },
    ),
]


async def list_tools(_ctx, _params):
    return ListToolsResult(tools=TOOLS)


async def call_tool(_ctx, params):
    args: dict[str, Any] = params.arguments or {}
    if params.name == "finance_file_preview":
        result = preview_file(
            args.get("file_base64", ""), args.get("filename", ""),
            args.get("mapping_json", "{}"), args.get("existing_transactions_json", "[]"),
        )
    elif params.name == "finance_file_apply_preview":
        result = preview_apply_request(args.get("preview_json", ""), confirm=args.get("confirm", False))
    else:
        raise ValueError(f"unknown tool: {params.name}")
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, sort_keys=True))])


async def main():
    server = Server("hades-actual-finance-import", on_list_tools=list_tools, on_call_tool=call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
