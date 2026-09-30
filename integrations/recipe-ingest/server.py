"""Private stdio MCP boundary for preview-first recipe URL ingestion."""

from __future__ import annotations

import json
import os
import time
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
MAX_API_KEY_BYTES = 8192


def _api_key() -> str:
    if not API_KEY_FILE:
        return ""
    path = Path(API_KEY_FILE)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Grocy API key file must be a regular non-symlink file")
    mode = path.stat().st_mode & 0o777
    if mode not in {0o600, 0o640}:
        raise ValueError("Grocy API key file must be mode 0600 or 0640")
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_API_KEY_BYTES:
        raise ValueError("Grocy API key file is empty or exceeds the bounded size")
    return raw.decode("utf-8").strip()


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


_importer = None
_PREVIEW_TTL_SECONDS = 15 * 60
_PREVIEW_CACHE_LIMIT = 32
_preview_cache: dict[str, tuple[float, dict]] = {}


def _get_importer():
    global _importer
    if _importer is None:
        _importer = GrocyRecipeImporter(_request)
    return _importer


def _cache_preview(preview: dict) -> None:
    token = preview.get("review_token") if isinstance(preview, dict) else None
    if not isinstance(token, str) or not token:
        return
    now = time.monotonic()
    for cached_token, (created, _value) in list(_preview_cache.items()):
        if now - created > _PREVIEW_TTL_SECONDS:
            _preview_cache.pop(cached_token, None)
    while len(_preview_cache) >= _PREVIEW_CACHE_LIMIT:
        _preview_cache.pop(next(iter(_preview_cache)))
    _preview_cache[token] = (now, preview)


def _cached_preview(token: str):
    entry = _preview_cache.get(token)
    if not entry:
        return None
    created, preview = entry
    if time.monotonic() - created > _PREVIEW_TTL_SECONDS:
        _preview_cache.pop(token, None)
        return None
    return preview


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
                         "Requires confirm=true; pass the exact preview or its short-lived "
                         "review_token; unresolved products are rejected."),
            inputSchema={"type": "object", "properties": {
                "preview": {"type": "object"},
                "review_token": {"type": "string"},
                "confirm": {"type": "boolean"},
            }, "required": ["confirm"]},
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
    importer = _get_importer()
    try:
        if tool_name == "recipe_url_preview":
            recipe = extract_from_url(str(args.get("url", "")))
            preview = _importer.preview(recipe)
            _cache_preview(preview)
            return _text(preview)
        if tool_name == "recipe_url_apply":
            preview = args.get("preview")
            if not isinstance(preview, dict):
                preview = _cached_preview(str(args.get("review_token", "")).strip())
            if preview is None:
                return _text({"outcome": "FAILED", "error": "Review token is missing or expired; create a new preview."})
            result = _importer.apply(preview, confirm=args.get("confirm") is True)
            if result.get("outcome") == "SUCCEEDED":
                token = preview.get("review_token")
                if isinstance(token, str):
                    _preview_cache.pop(token, None)
            return _text(result)
        if tool_name == "recipe_paste_preview":
            recipe = extract_from_paste(args.get("text", ""), args.get("source_url"))
            preview = _importer.preview(recipe)
            _cache_preview(preview)
            return _text(preview)
    except (ValueError, GrocyRequestError) as exc:
        return _text({"outcome": "FAILED", "error": str(exc)})
    raise ValueError(f"unknown tool: {tool_name}")


async def _list_tools(_context, _params):
    return await list_tools()


async def _call_tool(_context, params):
    return await call_tool(params.name, params.arguments)


async def main():
    server = Server("hades-recipe-ingest", on_list_tools=_list_tools, on_call_tool=_call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
