"""Bounded, anonymous public-page extraction for owner-facing research turns."""

from __future__ import annotations

import json
import gzip
import socket
import zlib
from html.parser import HTMLParser
from ipaddress import ip_address
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import urlparse

import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool


MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_TEXT_CHARS = 32_000
TIMEOUT_SECONDS = 20


class _VisiblePageParser(HTMLParser):
    """Keep readable text and title while ignoring executable page content."""

    _IGNORED = {"script", "style", "noscript", "template", "svg"}
    _BREAKS = {"br", "dd", "div", "dt", "h1", "h2", "h3", "h4", "li", "p", "pre", "section", "td", "th", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored = 0
        self._title = False
        self._title_parts: list[str] = []
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self._IGNORED:
            self._ignored += 1
        if tag == "title":
            self._title = True
        if not self._ignored and tag in self._BREAKS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._title = False
        if not self._ignored and tag in self._BREAKS:
            self._parts.append("\n")
        if tag in self._IGNORED and self._ignored:
            self._ignored -= 1

    def handle_data(self, data: str) -> None:
        if self._title:
            self._title_parts.append(data)
        if not self._ignored and data.strip():
            self._parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self._title_parts).split())[:512]

    @property
    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self._parts).splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(dict.fromkeys(lines))


def _safe_url(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("The page URL is missing or too long.")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("I can only read public HTTP or HTTPS pages.")
    if parsed.username or parsed.password:
        raise ValueError("Page URLs cannot contain embedded credentials.")
    host = parsed.hostname.rstrip(".")
    try:
        addresses = {ip_address(host)}
    except ValueError:
        try:
            addresses = {ip_address(info[4][0]) for info in socket.getaddrinfo(host, None)}
        except (OSError, ValueError):
            raise ValueError("The page host could not be resolved.") from None
    if not addresses or any(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
        for address in addresses
    ):
        raise ValueError("Private and local page targets are not allowed.")
    return value


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_public_page(url: str) -> dict[str, Any]:
    """Fetch static public HTML and return page evidence, never an action."""
    safe = _safe_url(url)
    request = Request(
        safe,
        headers={
            "Accept": "text/html, application/xhtml+xml;q=0.9",
            "User-Agent": "HADES public page reader/1.0",
        },
    )
    try:
        with build_opener(_SafeRedirectHandler).open(request, timeout=TIMEOUT_SECONDS) as response:
            final_url = _safe_url(response.geturl())
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                return {
                    "status": "FAILED",
                    "error": "The page returned a non-HTML document, so I could not read it as an article.",
                    "url": final_url,
                    "evidence": "NONE",
                }
            body = response.read(MAX_HTML_BYTES + 1)
            content_encoding = (response.headers.get("Content-Encoding") or "").lower()
            try:
                if "gzip" in content_encoding:
                    body = gzip.decompress(body)
                elif "deflate" in content_encoding:
                    body = zlib.decompress(body)
            except (OSError, zlib.error):
                return {
                    "status": "FAILED",
                    "error": "The page response could not be decoded safely.",
                    "url": safe,
                    "evidence": "NONE",
                }
    except HTTPError as exc:
        return {"status": "FAILED", "error": f"The page returned HTTP {exc.code}.", "url": safe, "evidence": "NONE"}
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", None)
        detail = str(reason or exc).lower()
        if "timed out" in detail or "timeout" in detail:
            message = "The page took too long to respond."
        else:
            message = "I found the page address, but could not retrieve it."
        return {"status": "FAILED", "error": message, "url": safe, "evidence": "NONE"}
    if len(body) > MAX_HTML_BYTES:
        return {"status": "FAILED", "error": "The page is larger than the safe reading limit.", "url": safe, "evidence": "NONE"}
    parser = _VisiblePageParser()
    try:
        parser.feed(body.decode("utf-8", errors="replace"))
    except Exception:
        return {"status": "FAILED", "error": "The page could not be parsed as readable HTML.", "url": final_url, "evidence": "NONE"}
    text = parser.text
    if not text:
        return {"status": "FAILED", "error": "The page loaded, but contained no readable text.", "url": final_url, "evidence": "NONE"}
    truncated = len(text) > MAX_TEXT_CHARS
    return {
        "status": "SUCCEEDED",
        "evidence": "PAGE",
        "url": safe,
        "final_url": final_url,
        "title": parser.title,
        "text": text[:MAX_TEXT_CHARS],
        "truncated": truncated,
        "content_type": "text/html",
        "bytes": len(body),
        "warnings": [
            "This is static page evidence; scripts, login state, and interactive content were not used.",
            "Use only claims supported by the extracted page text.",
        ],
    }


def _text(result: dict[str, Any]) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, sort_keys=True))])


async def _list_tools(_context, _params):
    return ListToolsResult(tools=[Tool(
        name="public_page_read",
        description=("Read a public static web page and return bounded page evidence. "
                     "This never logs in, clicks, submits forms, downloads files, or changes anything."),
        inputSchema={"type": "object", "properties": {"url": {"type": "string", "format": "uri", "maxLength": 2048}}, "required": ["url"]},
    )])


async def _call_tool(_context, params):
    if params.name != "public_page_read":
        raise ValueError(f"unknown tool: {params.name}")
    try:
        return _text(await anyio.to_thread.run_sync(read_public_page, (params.arguments or {}).get("url", "")))
    except ValueError as exc:
        return _text({"status": "FAILED", "error": str(exc), "evidence": "NONE"})


async def main():
    server = Server("hades-public-page-extract", on_list_tools=_list_tools, on_call_tool=_call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
