"""Policy proxy for the anonymous, read-oriented Playwright MCP surface."""

from __future__ import annotations

import ipaddress
import http.client
import json
import os
import re
import select
import signal
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from typing import Any


PACKAGE = os.environ.get("HADES_PLAYWRIGHT_MCP_PACKAGE", "@playwright/mcp@0.0.83")
ALLOWED_TOOLS = frozenset({
    "browser_navigate",
    "browser_snapshot",
    "browser_find",
    "browser_console_messages",
    "browser_network_requests",
    "browser_network_request",
    "browser_webmcp_list",
})
_ENV_DENYLIST = (
    "PLAYWRIGHT_MCP_STORAGE_STATE",
    "PLAYWRIGHT_MCP_USER_DATA_DIR",
    "PLAYWRIGHT_MCP_EXTENSION",
    "PLAYWRIGHT_MCP_SECRETS_FILE",
    "PLAYWRIGHT_MCP_ALLOW_UNRESTRICTED_FILE_ACCESS",
    "PLAYWRIGHT_MCP_CDP_ENDPOINT",
    "PLAYWRIGHT_MCP_CDP_HEADERS",
)


def _host_patterns() -> tuple[str, ...]:
    raw = os.environ.get("HADES_BROWSER_ALLOWED_HOSTS", "")
    hosts = tuple(item.strip().lower() for item in raw.split(",") if item.strip())
    if not hosts or any(" " in item or "/" in item or ":" in item for item in hosts):
        raise ValueError("HADES_BROWSER_ALLOWED_HOSTS must contain explicit comma-separated hostnames")
    return hosts


def _host_allowed(host: str, patterns: tuple[str, ...]) -> bool:
    host = host.lower().rstrip(".")
    return any(host == pattern or (pattern.startswith("*.") and host.endswith(pattern[1:])) for pattern in patterns)


def validate_navigation(url: Any) -> str:
    """Validate a public HTTP(S) navigation target against the configured allowlist."""
    if not isinstance(url, str) or len(url) > 2_048:
        raise ValueError("browser URL must be bounded text")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("browser navigation requires an HTTP(S) URL without embedded credentials")
    host = parsed.hostname.lower().rstrip(".")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_unspecified):
        if os.environ.get("HADES_BROWSER_ALLOW_PRIVATE_TARGETS") != "1":
            raise ValueError("private, loopback, link-local, and reserved browser targets are disabled")
    if not _host_allowed(host, _host_patterns()):
        raise ValueError("browser target is outside the explicit host allowlist")
    return url


def _strip_output_path(arguments: dict[str, Any]) -> dict[str, Any]:
    if any(key in arguments for key in ("filename", "path", "paths")):
        raise ValueError("browser output and filesystem arguments are not exposed")
    return arguments


def authorize_call(tool_name: Any, arguments: Any) -> dict[str, Any]:
    """Return sanitized arguments for one allowed anonymous browser call."""
    if not isinstance(tool_name, str) or tool_name not in ALLOWED_TOOLS:
        raise PermissionError("browser tool is outside the anonymous read surface")
    if not isinstance(arguments, dict):
        raise ValueError("browser tool arguments must be an object")
    sanitized = _strip_output_path(dict(arguments))
    if tool_name == "browser_navigate":
        sanitized["url"] = validate_navigation(sanitized.get("url"))
    return sanitized


def filtered_tools(tools: Any) -> list[dict[str, Any]]:
    """Filter an upstream tools/list response to the explicit read surface."""
    if not isinstance(tools, list):
        raise ValueError("upstream browser tool list is malformed")
    return [tool for tool in tools if isinstance(tool, dict) and tool.get("name") in ALLOWED_TOOLS]


def build_command(hosts: tuple[str, ...], config_path: str | None = None) -> list[str]:
    if not re.fullmatch(r"@playwright/mcp@0\.0\.83", PACKAGE):
        raise ValueError("Playwright MCP package must remain pinned to @playwright/mcp@0.0.83")
    command = [
        "npx", "--yes", PACKAGE,
        "--isolated", "--headless", "--browser", "chromium",
        "--block-service-workers", "--allowed-hosts", ",".join(hosts),
    ]
    if config_path:
        command.extend(["--config", config_path])
    return command


def _child_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in _ENV_DENYLIST:
        environment.pop(key, None)
    environment.update({
        "PLAYWRIGHT_MCP_ISOLATED": "true",
        "PLAYWRIGHT_MCP_HEADLESS": "true",
        "PLAYWRIGHT_MCP_BLOCK_SERVICE_WORKERS": "true",
    })
    return environment


def _validated_target_addresses(url: str, patterns: tuple[str, ...]) -> tuple[str, ...] | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    host = parsed.hostname.lower().rstrip(".")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if not _host_allowed(host, patterns):
        return None
    private_override = os.environ.get("HADES_BROWSER_ALLOW_PRIVATE_TARGETS") == "1"
    if address is not None:
        addresses = (address,)
    else:
        try:
            addresses = tuple(
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            )
        except (OSError, ValueError):
            return None
        if not addresses:
            return None
    if not private_override and any(
        item.is_private or item.is_loopback or item.is_link_local or item.is_reserved or item.is_unspecified
        for item in addresses
    ):
        return None
    return tuple(str(item) for item in addresses)


def _target_allowed(url: str, patterns: tuple[str, ...]) -> bool:
    return _validated_target_addresses(url, patterns) is not None


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to a validated IP while retaining hostname certificate checks."""

    def __init__(self, host: str, port: int, address: str, *, timeout: float):
        super().__init__(host, port, timeout=timeout)
        self._validated_address = address

    def connect(self) -> None:
        raw_socket = socket.create_connection((self._validated_address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


class _FilteringProxy:
    def __init__(self, patterns: tuple[str, ...]):
        self.patterns = patterns
        self.server = self._make_server()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def _make_server(self):
        patterns = self.patterns

        class Handler(BaseHTTPRequestHandler):
            def _deny(self):
                self.send_error(403, "browser target is outside HADES host policy")

            def _relay_http(self):
                if self.command not in {"GET", "HEAD"}:
                    self.send_error(403, "HADES anonymous browser permits only GET and HEAD")
                    return
                target = urlparse(self.path)
                addresses = _validated_target_addresses(self.path, patterns)
                if addresses is None:
                    self._deny()
                    return
                port = target.port or (443 if target.scheme == "https" else 80)
                connection = (_PinnedHTTPSConnection(target.hostname, port, addresses[0], timeout=30)
                              if target.scheme == "https" else
                              http.client.HTTPConnection(addresses[0], port, timeout=30))
                try:
                    body = None
                    length = self.headers.get("Content-Length")
                    if length:
                        body = self.rfile.read(min(int(length), 10 * 1024 * 1024))
                    path = target.path or "/"
                    if target.query:
                        path += "?" + target.query
                    headers = {key: value for key, value in self.headers.items() if key.lower() not in {"proxy-connection", "connection", "host"}}
                    headers["Host"] = target.netloc
                    connection.request(self.command, path, body=body, headers=headers)
                    response = connection.getresponse()
                    data = response.read(10 * 1024 * 1024 + 1)
                    self.send_response(response.status, response.reason)
                    for key, value in response.getheaders():
                        if key.lower() not in {"connection", "transfer-encoding"}:
                            self.send_header(key, value)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data[:10 * 1024 * 1024])
                except Exception:
                    self.send_error(502, "browser upstream request failed")
                finally:
                    connection.close()

            def do_CONNECT(self):
                host, separator, port_text = self.path.partition(":")
                port = int(port_text or "443") if separator and port_text.isdigit() else 443
                target_url = f"https://{host}:{port}"
                addresses = _validated_target_addresses(target_url, patterns)
                if addresses is None:
                    self._deny()
                    return
                try:
                    remote = socket.create_connection((addresses[0], port), timeout=30)
                    self.send_response(200, "Connection Established")
                    self.end_headers()
                    sockets = [self.connection, remote]
                    while True:
                        ready, _, _ = select.select(sockets, [], [], 30)
                        if not ready:
                            break
                        for source in ready:
                            data = source.recv(64 * 1024)
                            if not data:
                                return
                            (remote if source is self.connection else self.connection).sendall(data)
                except Exception:
                    self.send_error(502, "browser CONNECT failed")
                finally:
                    try:
                        remote.close()
                    except UnboundLocalError:
                        pass

            def do_GET(self): self._relay_http()
            def do_HEAD(self): self._relay_http()
            def do_POST(self): self._relay_http()
            def do_PUT(self): self._relay_http()
            def do_OPTIONS(self): self._relay_http()
            def log_message(self, *_args): pass

        return ThreadingHTTPServer(("127.0.0.1", 0), Handler)

    @property
    def port(self) -> int:
        return int(self.server.server_address[1])

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


class Upstream:
    def __init__(self, hosts: tuple[str, ...]):
        self.request_proxy = _FilteringProxy(hosts)
        self.config_directory = tempfile.TemporaryDirectory(prefix="hades-browser-readonly-")
        config_path = os.path.join(self.config_directory.name, "playwright.json")
        init_script = os.path.join(os.path.dirname(__file__), "read-only-network.js")
        with open(config_path, "w", encoding="utf-8") as config_file:
            json.dump({"browser": {
                "initScript": [init_script],
                "contextOptions": {"serviceWorkers": "block"},
            }}, config_file)
        self.process = subprocess.Popen(
            build_command(hosts, config_path) + ["--proxy-server", f"http://127.0.0.1:{self.request_proxy.port}", "--proxy-bypass", "none"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=sys.stderr, text=True, bufsize=1, env=_child_environment(),
            start_new_session=True,
        )

    def request(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("browser upstream streams are unavailable")
        self.process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.process.stdin.flush()
        request_id = message.get("id")
        if request_id is None:
            return None
        for line in self.process.stdout:
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(response, dict) and response.get("id") == request_id:
                return response
        raise RuntimeError("browser upstream closed before responding")

    def close(self) -> None:
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
            self.process.wait(timeout=3)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.process.wait(timeout=3)
        self.request_proxy.close()
        self.config_directory.cleanup()


def _error(message: dict[str, Any], error: Exception) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": -32001, "message": str(error)}}


def main() -> None:
    try:
        hosts = _host_patterns()
        upstream = Upstream(hosts)
    except Exception as exc:
        print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": str(exc)}}), flush=True)
        raise SystemExit(1)
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("MCP message must be an object")
                method = message.get("method")
                if method == "tools/list":
                    response = upstream.request(message)
                    if response and isinstance(response.get("result"), dict):
                        response["result"]["tools"] = filtered_tools(response["result"].get("tools"))
                    if response is not None:
                        print(json.dumps(response, separators=(",", ":")), flush=True)
                    continue
                if method == "tools/call":
                    params = message.get("params")
                    if not isinstance(params, dict):
                        raise ValueError("browser tools/call parameters are malformed")
                    params = dict(params)
                    params["arguments"] = authorize_call(params.get("name"), params.get("arguments", {}))
                    message["params"] = params
                response = upstream.request(message)
                if response is not None:
                    print(json.dumps(response, separators=(",", ":")), flush=True)
            except Exception as exc:
                print(json.dumps(_error(message if isinstance(locals().get("message"), dict) else {}, exc), separators=(",", ":")), flush=True)
    finally:
        upstream.close()


if __name__ == "__main__":
    main()
