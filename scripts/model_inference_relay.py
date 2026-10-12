#!/usr/bin/env python3
"""Fixed-destination, inference-only HTTP relay for disposable Hermes workers."""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit

MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 32 * 1024 * 1024


class RelayError(RuntimeError):
    pass


def parse_upstream(value: str) -> tuple[str, int]:
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise RelayError("upstream port is invalid") from exc
    if (parsed.scheme != "http" or not parsed.hostname or not port
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/", "/v1"}):
        raise RelayError("upstream must be a fixed plain-HTTP origin with optional /v1 path")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError as exc:
        raise RelayError("upstream must use a fixed IP address; DNS is not permitted") from exc
    if (address.version != 4 or not address.is_private or address.is_loopback
            or address.is_multicast or address.is_link_local or address.is_unspecified
            or address.is_reserved):
        raise RelayError("upstream IP is outside the approved private-address class")
    return str(address), port


def make_handler(host: str, port: int, model: str, metrics_file: Path | None = None):
    metrics_lock = threading.Lock()
    request_count = 0

    class InferenceHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _reply(self, status: int, body: bytes, content_type: str = "application/json") -> None:
            if "\r" in content_type or "\n" in content_type:
                content_type = "application/json"
            self.close_connection = True
            self.close_connection = True
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def _request_body(self) -> bytes | None:
            if self.headers.get("Transfer-Encoding") is not None:
                self._reply(400, b'{"error":"transfer encoding denied"}')
                return None
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1:
                self._reply(400, b'{"error":"one content length is required"}')
                return None
            raw_length = lengths[0]
            if not raw_length.isdecimal() or int(raw_length) > MAX_REQUEST_BYTES:
                self._reply(413, b'{"error":"request size denied"}')
                return None
            return self.rfile.read(int(raw_length))

        def _forward(self, method: str, path: str, body: bytes = b"") -> None:
            nonlocal request_count
            started = time.perf_counter()
            status_code = 502
            connection = http.client.HTTPConnection(host, port, timeout=300)
            try:
                connection.request(
                    method, path, body=body,
                    headers={"Content-Type": "application/json", "Connection": "close"},
                )
                response = connection.getresponse()
                payload = response.read(MAX_RESPONSE_BYTES + 1)
                if len(payload) > MAX_RESPONSE_BYTES:
                    self._reply(502, b'{"error":"inference response exceeded relay bound"}')
                    return
                status_code = response.status
                self._reply(response.status, payload, response.getheader("Content-Type", "application/json"))
            except (OSError, http.client.HTTPException):
                self._reply(502, b'{"error":"approved inference endpoint unavailable"}')
            finally:
                connection.close()
                if metrics_file is not None:
                    with metrics_lock:
                        request_count += 1
                        row = {
                            "request": request_count,
                            "elapsed_ms": max(0, int((time.perf_counter() - started) * 1000)),
                            "status": status_code,
                        }
                        with metrics_file.open("a", encoding="utf-8") as stream:
                            stream.write(json.dumps(row, separators=(",", ":")) + "\n")
            self.close_connection = True

        def do_GET(self) -> None:  # noqa: N802
            self._reply(403, b'{"error":"route denied"}')

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/chat/completions":
                self._reply(403, b'{"error":"route denied"}')
                return
            body = self._request_body()
            if body is None:
                return
            try:
                document = json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._reply(400, b'{"error":"invalid JSON"}')
                return
            if (not isinstance(document, dict) or document.get("model") != model
                    or document.get("stream") is True):
                self._reply(403, b'{"error":"model or streaming request denied"}')
                return
            self._forward("POST", "/v1/chat/completions", body)

        def do_PUT(self) -> None:  # noqa: N802
            self._reply(403, b'{"error":"method denied"}')

        def do_DELETE(self) -> None:  # noqa: N802
            self._reply(403, b'{"error":"method denied"}')

        def do_PATCH(self) -> None:  # noqa: N802
            self._reply(403, b'{"error":"method denied"}')

    return InferenceHandler


class UnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False


def serve(socket_path: Path, upstream: str, model: str, metrics_file: Path | None = None) -> None:
    host, port = parse_upstream(upstream)
    if not model or len(model) > 256 or any(ch in model for ch in "\r\n\0"):
        raise RelayError("model identifier is invalid")
    socket_path = socket_path.absolute()
    socket_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if socket_path.exists():
        raise RelayError("refusing to replace an existing relay path")
    if metrics_file is not None:
        metrics_file = metrics_file.absolute()
        if (metrics_file == socket_path or metrics_file.exists()
                or metrics_file.parent != socket_path.parent
                or not metrics_file.parent.is_dir()):
            raise RelayError("metrics path is unavailable")
        descriptor = metrics_file.open("x", encoding="utf-8")
        descriptor.close()
        metrics_file.chmod(0o600)
    server = UnixHTTPServer(str(socket_path), make_handler(host, port, model, metrics_file))
    socket_path.chmod(0o600)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        socket_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--metrics-file", type=Path)
    args = parser.parse_args()
    serve(args.socket, args.upstream, args.model, args.metrics_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
