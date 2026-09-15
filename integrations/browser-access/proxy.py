"""Policy proxy for the anonymous, read-oriented Playwright MCP surface."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
import sys
from urllib.parse import urlparse
from typing import Any


PACKAGE = os.environ.get("HADES_PLAYWRIGHT_MCP_PACKAGE", "@playwright/mcp@0.0.81")
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


def build_command(hosts: tuple[str, ...]) -> list[str]:
    if not re.fullmatch(r"@playwright/mcp@0\.0\.81", PACKAGE):
        raise ValueError("Playwright MCP package must remain pinned to @playwright/mcp@0.0.81")
    return [
        "npx", "--yes", PACKAGE,
        "--isolated", "--headless", "--browser", "chromium",
        "--block-service-workers", "--allowed-hosts", ",".join(hosts),
    ]


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


class Upstream:
    def __init__(self, hosts: tuple[str, ...]):
        self.process = subprocess.Popen(
            build_command(hosts), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=sys.stderr, text=True, bufsize=1, env=_child_environment(),
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
        self.process.terminate()


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
