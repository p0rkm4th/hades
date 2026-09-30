#!/usr/bin/env python3
"""Runtime bounds for compressed public-page responses and redirects."""

import gzip
import importlib.util
import sys
import types
import zlib
from pathlib import Path
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.request import Request


# Load the reader without requiring the optional MCP runtime in the test host.
anyio = types.ModuleType("anyio")
mcp = types.ModuleType("mcp")
mcp_server = types.ModuleType("mcp.server")
mcp_lowlevel = types.ModuleType("mcp.server.lowlevel")
mcp_lowlevel.Server = lambda *args, **kwargs: None
mcp_stdio = types.ModuleType("mcp.server.stdio")
mcp_stdio.stdio_server = lambda: None
mcp_types = types.ModuleType("mcp.types")
for name in ("CallToolResult", "ListToolsResult", "TextContent", "Tool"):
    setattr(mcp_types, name, type(name, (), {"__init__": lambda self, **kwargs: self.__dict__.update(kwargs)}))
sys.modules.update({
    "anyio": anyio,
    "mcp": mcp,
    "mcp.server": mcp_server,
    "mcp.server.lowlevel": mcp_lowlevel,
    "mcp.server.stdio": mcp_stdio,
    "mcp.types": mcp_types,
})
source = Path("integrations/web-extract/server.py")
spec = importlib.util.spec_from_file_location("hades_web_extract_runtime", source)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class Headers:
    def __init__(self, encoding):
        self.encoding = encoding

    def get_content_type(self):
        return "text/html"

    def get(self, key, default=None):
        return self.encoding if key.lower() == "content-encoding" else default


class Response:
    def __init__(self, body, encoding):
        self.body = body
        self.headers = Headers(encoding)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return "https://public.example/article"

    def read(self, _limit):
        return self.body


class Opener:
    def __init__(self, response):
        self.response = response

    def open(self, _request, timeout):
        assert timeout == reader.TIMEOUT_SECONDS
        return self.response


def read_fixture(body, encoding):
    safe_url = reader._safe_url
    build_opener = reader.build_opener
    reader._safe_url = lambda value: value  # Network/DNS policy is exercised separately below.
    reader.build_opener = lambda *_handlers: Opener(Response(body, encoding))
    try:
        return reader.read_public_page("https://public.example/article")
    finally:
        reader._safe_url = safe_url
        reader.build_opener = build_opener


small_html = (
    b'<html><head><meta property="article:published_time" content="2021-06-07T08:09:10Z">'
    b'<time datetime="2026-09-27" itemprop="dateModified">updated today</time>'
    b'</head><title>Fixture</title><body><p>Readable evidence.</p></body></html>'
)
modified_only = reader._VisiblePageParser()
modified_only.feed('<time itemprop="dateModified" datetime="2026-09-27">updated today</time>')
assert modified_only.publisher_date is None
for encoding, body in (
    ("gzip", gzip.compress(small_html)),
    ("deflate", zlib.compress(small_html)),
):
    result = read_fixture(body, encoding)
    assert result["status"] == "SUCCEEDED" and "Readable evidence." in result["text"]
    assert result["publisher_date"] == "2021-06-07T08:09:10Z"

bomb = b"x" * (reader.MAX_HTML_BYTES + 4096)
for encoding, body in (
    ("gzip", gzip.compress(bomb)),
    ("deflate", zlib.compress(bomb)),
):
    result = read_fixture(body, encoding)
    assert result["status"] == "FAILED"
    assert "safe reading limit" in result["error"]

truncated = read_fixture(gzip.compress(small_html)[:-4], "gzip")
assert truncated["status"] == "FAILED" and "decoded safely" in truncated["error"]

original_getaddrinfo = reader.socket.getaddrinfo
original_create_connection = reader.socket.create_connection
public_info = (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 80))
private_info = (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80))
connect_calls = []
try:
    answers = iter((public_info, private_info))
    reader.socket.getaddrinfo = lambda *_args, **_kwargs: [next(answers)]
    reader.socket.create_connection = lambda *args, **_kwargs: connect_calls.append(args) or object()
    reader._safe_url("http://rebind.example/article")  # Initial validation sees a public address.
    try:
        reader._PinnedHTTPConnection("rebind.example", timeout=1).connect()
    except ValueError as exc:
        assert "globally routable unicast" in str(exc)
    else:
        raise AssertionError("connection accepted a private address after DNS changed")
    assert connect_calls == []

    reader.socket.getaddrinfo = lambda *_args, **_kwargs: [public_info]
    reader._PinnedHTTPConnection("stable.example", timeout=1).connect()
    assert connect_calls[-1][0] == ("93.184.216.34", 80)

    validated_connection_count = len(connect_calls)
    for non_public_target in (
        "100.64.0.1", "224.0.0.1", "239.1.2.3", "ff02::1",
        "::ffff:127.0.0.1", "64:ff9b::7f00:1",
    ):
        try:
            reader._PinnedHTTPConnection(non_public_target, port=80, timeout=1).connect()
        except ValueError as exc:
            assert "globally routable unicast" in str(exc)
        else:
            raise AssertionError(f"non-global or multicast target was accepted: {non_public_target}")
    assert len(connect_calls) == validated_connection_count

    # Some system resolvers interpret these non-standard IPv4 spellings as
    # loopback. They must still be rejected based on the resolved address.
    reader.socket.getaddrinfo = lambda *_args, **_kwargs: [private_info]
    for alternate_loopback in ("2130706433", "0177.0.0.1", "0x7f000001"):
        try:
            reader._safe_url(f"http://{alternate_loopback}/private")
        except ValueError as exc:
            assert "globally routable unicast" in str(exc)
        else:
            raise AssertionError(f"alternate loopback spelling was accepted: {alternate_loopback}")
        try:
            reader._SafeRedirectHandler().redirect_request(
                Request("https://public.example/"), None, 302, "Found", {},
                f"http://{alternate_loopback}/private",
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"redirect to alternate loopback spelling was accepted: {alternate_loopback}")
    assert len(connect_calls) == validated_connection_count

    class FakeTLSContext:
        def wrap_socket(self, sock, *, server_hostname):
            assert server_hostname == "secure.example"
            return (sock, server_hostname)

    tls_socket = object()
    reader.socket.getaddrinfo = lambda *_args, **_kwargs: [public_info]
    reader.socket.create_connection = lambda *args, **_kwargs: tls_socket
    secure = reader._PinnedHTTPSConnection(
        "secure.example", timeout=1, context=FakeTLSContext(),
    )
    secure.connect()
    assert secure.sock == (tls_socket, "secure.example")

    https_handler = reader._PinnedHTTPSHandler()
    https_handler.do_open = lambda connection, request, **kwargs: (connection, request, kwargs)
    connection, request, kwargs = https_handler.https_open(Request("https://secure.example/article"))
    assert connection is reader._PinnedHTTPSConnection
    assert request.full_url == "https://secure.example/article"
    assert kwargs == {"context": https_handler._context}
finally:
    reader.socket.getaddrinfo = original_getaddrinfo
    reader.socket.create_connection = original_create_connection

handler = reader._SafeRedirectHandler()
for target in (
    "http://127.0.0.1/private",
    "http://100.64.0.1/private",
    "http://224.0.0.1/private",
    "http://[ff02::1]/private",
    "http://[::ffff:127.0.0.1]/private",
    "http://[64:ff9b::7f00:1]/private",
    "http://user:secret@example.com/",
):
    try:
        handler.redirect_request(Request("https://public.example/"), None, 302, "Found", {}, target)
    except ValueError:
        pass
    else:
        raise AssertionError(f"unsafe redirect was accepted: {target}")


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.request_count += 1
        self.server.paths.append(self.path)
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header(
                "Location",
                f"http://127.0.0.1:{self.server.server_port}/private",
            )
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/safe-redirect":
            self.send_response(302)
            self.send_header(
                "Location",
                f"http://fixture.invalid:{self.server.server_port}/article",
            )
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(small_html)

    def log_message(self, *_args):
        pass


httpd = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
httpd.request_count = 0
httpd.paths = []
thread = Thread(target=httpd.serve_forever, daemon=True)
thread.start()
original_safe_url = reader._safe_url
original_public_addresses = reader._public_addresses
try:
    # The test-only resolver pins a synthetic hostname to the local fixture;
    # production checks continue to reject this address.
    reader._safe_url = lambda value: value
    reader._public_addresses = lambda _host, _port: ["127.0.0.1"]
    integration = reader.read_public_page(
        f"http://fixture.invalid:{httpd.server_port}/article",
    )
    assert integration["status"] == "SUCCEEDED", integration
    assert "Readable evidence." in integration["text"]
    assert integration["publisher_date"] == "2021-06-07T08:09:10Z"
    assert httpd.request_count == 1

    # Exercise the complete collector -> actual page reader -> urllib redirect
    # chain. The synthetic resolver exception is scoped to this local fixture.
    import importlib.util
    research_spec = importlib.util.spec_from_file_location(
        "hades_public_research_redirect_runtime",
        "integrations/public-research/research.py",
    )
    research = importlib.util.module_from_spec(research_spec)
    research_spec.loader.exec_module(research)
    final_request_seen = [False]
    original_do_get = FixtureHandler.do_GET

    def observe_final_request(self):
        if self.path == "/article":
            final_request_seen[0] = True
        return original_do_get(self)

    FixtureHandler.do_GET = observe_final_request
    original_public_addresses_for_timestamp = reader._public_addresses
    reader._public_addresses = lambda _host, _port: ["127.0.0.1"]
    clock_events = []

    def ordered_clock():
        clock_events.append(final_request_seen[0])
        return f"2026-09-27T12:00:{len(clock_events):02d}Z"

    try:
        redirected_url = f"http://fixture.invalid:{httpd.server_port}/safe-redirect"
        collected = research.research_public_sources(
            "Example public release", subject_class="organization",
            search=lambda _query: {"results": [{
                "title": "Release", "url": redirected_url,
                "content": "Public release information.",
            }]},
            read_page=reader.read_public_page,
            clock=ordered_clock,
        )
        page = next(
            row for row in collected["page_reads"]
            if row["evidence_type"] == "STATIC_PAGE"
        )
        assert collected["status"] == "SUCCEEDED", collected
        assert page["url"] == redirected_url
        assert page["final_url"] == f"http://fixture.invalid:{httpd.server_port}/article"
        assert page["retrieved_at_utc"] == "2026-09-27T12:00:02Z"
        assert clock_events == [False, True, True], clock_events
    finally:
        reader._public_addresses = original_public_addresses_for_timestamp
        FixtureHandler.do_GET = original_do_get

    reader._safe_url = original_safe_url
    fixture_resolution_count = [0]

    def redirect_fixture_addresses(host, port):
        if host == "fixture.invalid":
            fixture_resolution_count[0] += 1
            return ["93.184.216.34"] if fixture_resolution_count[0] == 1 else ["127.0.0.1"]
        return original_public_addresses(host, port)

    reader._public_addresses = redirect_fixture_addresses
    try:
        redirect_result = reader.read_public_page(f"http://fixture.invalid:{httpd.server_port}/redirect")
    except ValueError as exc:
        assert "globally routable unicast" in str(exc)
    else:
        raise AssertionError(f"actual redirect chain accepted a loopback target: {redirect_result}; paths={httpd.paths}")
    assert httpd.request_count == 4  # Only the denied redirect target receives no request.
    assert "/private" not in httpd.paths
finally:
    reader._safe_url = original_safe_url
    reader._public_addresses = original_public_addresses
    httpd.shutdown()
    thread.join(timeout=2)
    httpd.server_close()

print("PASS gzip and deflate pages within the decompressed limit")
print("PASS gzip and deflate expansion bombs fail before exceeding the output bound")
print("PASS truncated compressed pages fail safely")
print("PASS connection uses a validated IP and rejects a changed private DNS answer")
print("PASS non-global, multicast, IPv4-mapped IPv6, and NAT64 loopback targets are rejected before socket creation and on redirects")
print("PASS alternate dotted-octal, integer, and hexadecimal IPv4 loopback spellings are rejected from resolved-address evidence")
print("PASS HTTPS handler carries the configured TLS context to the pinned connection")
print("PASS redirects to loopback or credential-bearing URLs are rejected")
print("PASS actual urllib opener fetches a loopback-only synthetic HTTP fixture through the pinned transport")
print("PASS collector timestamps the final page fetch after its actual HTTP redirect")
print("PASS actual redirect chain rejects a loopback destination before its second request")
