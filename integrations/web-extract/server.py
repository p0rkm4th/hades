"""Bounded, anonymous public-page extraction for owner-facing research turns."""

from __future__ import annotations

import http.client
import json
import socket
import ssl
import zlib
from datetime import datetime
from html.parser import HTMLParser
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPHandler,
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

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
        self._publisher_date: str | None = None

    @staticmethod
    def _valid_publisher_date(value: str | None) -> str | None:
        if not value or len(value) > 80:
            return None
        normalized = value.strip()
        try:
            datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            return None
        return normalized

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {name.lower(): value for name, value in attrs if value is not None}
        if self._publisher_date is None and tag == "meta":
            marker = (values.get("property") or values.get("name") or values.get("itemprop") or "").lower()
            if marker in {"article:published_time", "og:published_time", "datepublished"}:
                self._publisher_date = self._valid_publisher_date(values.get("content"))
        if self._publisher_date is None and tag == "time" and "datepublished" in (values.get("itemprop") or "").lower():
            self._publisher_date = self._valid_publisher_date(values.get("datetime"))
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
    def publisher_date(self) -> str | None:
        return self._publisher_date

    @property
    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self._parts).splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(dict.fromkeys(lines))


def _public_addresses(host: str, port: int | None) -> list[str]:
    try:
        addresses = [ip_address(host)]
    except ValueError:
        try:
            addresses = list(dict.fromkeys(
                ip_address(info[4][0])
                for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            ))
        except (OSError, ValueError):
            raise ValueError("The page host could not be resolved.") from None
    if not addresses or any(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
        or not address.is_global
        or address.is_multicast
        for address in addresses
    ):
        raise ValueError("Only globally routable unicast page targets are allowed.")
    return [str(address) for address in addresses]


def _safe_url(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("The page URL is missing or too long.")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("I can only read public HTTP or HTTPS pages.")
    if parsed.username or parsed.password:
        raise ValueError("Page URLs cannot contain embedded credentials.")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        raise ValueError("The page URL has an invalid port.") from None
    _public_addresses(parsed.hostname.rstrip("."), port)
    return value


def _connect_to_public_address(host: str, port: int, timeout: float | None, source_address):
    addresses = _public_addresses(host.rstrip("."), port)
    last_error = None
    for address in addresses:
        try:
            # Connect to the exact validated IP. Do not ask the resolver to
            # resolve the hostname a second time after policy validation.
            return socket.create_connection((address, port), timeout, source_address)
        except OSError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise OSError("The page host has no usable address.")


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def connect(self) -> None:
        self.sock = _connect_to_public_address(
            self.host, self.port, self.timeout, self.source_address,
        )
        if self._tunnel_host:
            self._tunnel()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self) -> None:
        sock = _connect_to_public_address(
            self.host, self.port, self.timeout, self.source_address,
        )
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
            sock = self.sock
        context = self._context or ssl.create_default_context()
        self.sock = context.wrap_socket(sock, server_hostname=self.host)


class _PinnedHTTPHandler(HTTPHandler):
    def http_open(self, req):
        return self.do_open(_PinnedHTTPConnection, req)


class _PinnedHTTPSHandler(HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_PinnedHTTPSConnection, req, context=self._context)


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
        with build_opener(
            ProxyHandler({}), _SafeRedirectHandler(),
            _PinnedHTTPHandler(), _PinnedHTTPSHandler(),
        ).open(request, timeout=TIMEOUT_SECONDS) as response:
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
                    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
                    body = decompressor.decompress(body, MAX_HTML_BYTES + 1)
                    if len(body) > MAX_HTML_BYTES or decompressor.unconsumed_tail:
                        return {
                            "status": "FAILED",
                            "error": "The page is larger than the safe reading limit.",
                            "url": safe,
                            "evidence": "NONE",
                        }
                    if not decompressor.eof or decompressor.unused_data:
                        raise zlib.error("incomplete or trailing gzip data")
                elif "deflate" in content_encoding:
                    decompressor = zlib.decompressobj()
                    body = decompressor.decompress(body, MAX_HTML_BYTES + 1)
                    if len(body) > MAX_HTML_BYTES or decompressor.unconsumed_tail:
                        return {
                            "status": "FAILED",
                            "error": "The page is larger than the safe reading limit.",
                            "url": safe,
                            "evidence": "NONE",
                        }
                    if not decompressor.eof or decompressor.unused_data:
                        raise zlib.error("incomplete or trailing deflate data")
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
        "publisher_date": parser.publisher_date,
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
