"""Private stdio MCP boundary for preview-first recipe URL ingestion."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from recipe_ingest import GrocyRecipeImporter, GrocyRequestError, extract_from_paste, extract_from_url


BASE_URL = (
    os.environ.get("GROCY_URL")
    or os.environ.get("HADES_GROCY_URL")
    or "http://127.0.0.1:7003"
).rstrip("/")
API_KEY_FILE = os.environ.get("GROCY_API_KEY_FILE") or os.environ.get(
    "HADES_GROCY_API_KEY_FILE", ""
)


def _api_key() -> str:
    if not API_KEY_FILE:
        return ""
    return Path(API_KEY_FILE).read_text(encoding="utf-8").strip()


def _request(method: str, path: str, payload=None):
    key = _api_key()
    if not key:
        raise GrocyRequestError("Grocy recipe ingestion is not configured.")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={"GROCY-API-KEY": key, "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GrocyRequestError(str(exc), after_mutation=method != "GET") from exc


def _text(result: dict) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, sort_keys=True))])


async def list_tools():
    return ListToolsResult(tools=[
        Tool(
            name="recipe_url_preview",
            description=("Fetch a public recipe URL and return a reviewable preview. "
                         "This never writes Grocy or creates products."),
            inputSchema={"type": "object", "properties": {"url": {"type": "string", "format": "uri"}}, "required": ["url"]},
        ),
        Tool(
            name="recipe_url_apply",
            description=("Apply a previously reviewed recipe preview to canonical Grocy. "
                         "Requires confirm=true; unresolved products are rejected."),
            inputSchema={"type": "object", "properties": {"preview": {"type": "object"}, "confirm": {"type": "boolean"}}, "required": ["preview", "confirm"]},
        ),
        Tool(
            name="recipe_paste_preview",
            description=("Normalize pasted recipe text, HTML, or JSON-LD and return a reviewable preview. "
                         "This never writes Grocy or creates products."),
            inputSchema={"type": "object", "properties": {
                "text": {"type": "string", "maxLength": 2097152},
                "source_url": {"type": "string"},
            }, "required": ["text"]},
        ),
    ])


async def call_tool(tool_name, args):
    args = args or {}
    importer = GrocyRecipeImporter(_request)
    try:
        if tool_name == "recipe_url_preview":
            recipe = extract_from_url(str(args.get("url", "")))
            return _text(importer.preview(recipe))
        if tool_name == "recipe_url_apply":
            return _text(importer.apply(args.get("preview", {}), confirm=args.get("confirm") is True))
        if tool_name == "recipe_paste_preview":
            recipe = extract_from_paste(args.get("text", ""), args.get("source_url"))
            return _text(importer.preview(recipe))
    except (ValueError, GrocyRequestError) as exc:
        return _text({"outcome": "FAILED", "error": str(exc)})
    raise ValueError(f"unknown tool: {tool_name}")


async def main():
    server = Server("hades-recipe-ingest")
    server.list_tools()(list_tools)
    server.call_tool()(call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
