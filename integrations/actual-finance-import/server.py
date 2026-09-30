"""Preview-only MCP surface for local Actual Budget file intake."""

from __future__ import annotations

import json
from typing import Any

import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from service import inspect_file, preview_apply_request, preview_file


TOOLS = [
    Tool(
        name="finance_file_inspect",
        description=(
            "Identify a local CSV, QIF, OFX, QFX, or CAMT statement and explain "
            "what is missing before preview. This is write-free and does not need an account ID."
        ),
        inputSchema={
            "type": "object",
            "properties": {"file_base64": {"type": "string"}, "filename": {"type": "string"}},
            "required": ["file_base64", "filename"],
        },
    ),
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
                "target_account_id": {"type": "string", "description": "Explicit Actual Budget account ID; names are not accepted."},
                "mapping_json": {"type": "string", "description": "CSV column mapping JSON object."},
                "existing_transactions_json": {"type": "string", "description": "Optional canonical rows for duplicate analysis."},
            },
            "required": ["file_base64", "filename", "target_account_id"],
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


async def list_tools():
    return ListToolsResult(tools=TOOLS)


async def call_tool(tool_name, args):
    args: dict[str, Any] = args or {}
    if tool_name == "finance_file_inspect":
        result = inspect_file(args.get("file_base64", ""), args.get("filename", ""))
    elif tool_name == "finance_file_preview":
        result = preview_file(
            args.get("file_base64", ""), args.get("filename", ""), args.get("target_account_id", ""),
            args.get("mapping_json", "{}"), args.get("existing_transactions_json", "[]"),
        )
    elif tool_name == "finance_file_apply_preview":
        result = preview_apply_request(args.get("preview_json", ""), confirm=args.get("confirm", False))
    else:
        raise ValueError(f"unknown tool: {tool_name}")
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, sort_keys=True))])


async def _list_tools(_context, _params):
    return await list_tools()


async def _call_tool(_context, params):
    return await call_tool(params.name, params.arguments)


async def main():
    server = Server(
        "hades-actual-finance-import",
        on_list_tools=_list_tools,
        on_call_tool=_call_tool,
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
