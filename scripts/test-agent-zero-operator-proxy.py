#!/usr/bin/env python3
"""Exercise the optional dual-origin cookie-filtering Nginx gateway."""

from __future__ import annotations

import base64
import hashlib
import http.client
import importlib.util
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "operator_session_auth", ROOT / "integrations/operator-access/session_auth.py"
)
assert spec and spec.loader
session_auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session_auth)

observed: dict[str, list[dict[str, str]]] = {"webui": [], "agent_zero": []}
observed_lock = threading.Lock()
directory_role = {"owner-subject": "owner", "household-subject": "household"}
auth_failures: list[str] = []


def _respond(handler: BaseHTTPRequestHandler, body: bytes, status: int = 200) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class WebUiFixture(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        with observed_lock:
            observed["webui"].append({
                "cookie": self.headers.get("Cookie", ""),
                "authorization": self.headers.get("Authorization", ""),
                "path": self.path,
            })
        _respond(self, json.dumps({"upstream": "webui", "path": self.path}).encode())

    def log_message(self, _format: str, *_args: object) -> None:
        return


class AgentZeroFixture(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        with observed_lock:
            observed["agent_zero"].append({
                "cookie": self.headers.get("Cookie", ""),
                "authorization": self.headers.get("Authorization", ""),
                "user": self.headers.get("X-Hades-Authenticated-User", ""),
                "groups": self.headers.get("X-Hades-Authenticated-Groups", ""),
                "path": self.path,
                "upgrade": self.headers.get("Upgrade", ""),
            })
        if self.headers.get("Upgrade", "").casefold() == "websocket":
            key = self.headers.get("Sec-WebSocket-Key", "")
            accept = base64.b64encode(
                hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
            ).decode()
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            self.wfile.write(b"\x81\x02OK")
            self.wfile.flush()
            return
        _respond(self, json.dumps({"upstream": "agent-zero", "path": self.path}).encode())

    def log_message(self, _format: str, *_args: object) -> None:
        return


class AuthFixture(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/webui-cookie":
            try:
                cookie = session_auth.webui_cookie(self.headers)
            except session_auth.OperatorAuthorizationError:
                self.send_response(401)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(204)
            if cookie:
                self.send_header("X-Hades-WebUI-Cookie", cookie)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path != "/authorize":
            self.send_error(404)
            return
        endpoint = FakeSessionEndpoint()
        try:
            session_auth.authorize_request(
                self.headers,
                webui_endpoint="http://127.0.0.1:1",
                directory_authority=lambda subject: SimpleNamespace(
                    active=True,
                    subject=subject,
                    role=directory_role.get(subject, "household"),
                ),
                opener=endpoint,
            )
            cookie = session_auth.agent_zero_cookie(self.headers)
        except (session_auth.OperatorAuthorizationError, ValueError) as exc:
            auth_failures.append(f"{self.path}:{exc}")
            self.send_response(401)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(204)
        if cookie:
            self.send_header("X-Hades-Agent-Zero-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, _format: str, *_args: object) -> None:
        return


class Response:
    def __init__(self, subject: str) -> None:
        self.raw = json.dumps({"id": subject, "email": "synthetic@example.test"}).encode()

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.raw[:limit]


class FakeSessionEndpoint:
    def open(self, request, timeout: float) -> Response:  # type: ignore[no-untyped-def]
        assert timeout == 4.0
        token = ""
        cookie_header = request.get_header("Cookie", "") or request.headers.get("Cookie", "")
        for pair in cookie_header.split(";"):
            name, _, value = pair.strip().partition("=")
            if name == "token":
                token = value
        if token == "owner-token":
            return Response("owner-subject")
        if token == "household-token":
            return Response("household-subject")
        raise HTTPError(request.full_url, 401, "unauthorized", {}, None)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _serve(handler) -> ThreadingHTTPServer:  # type: ignore[no-untyped-def]
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _request(port: int, path: str, cookie: str, authorization: str = "") -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    headers = {"Cookie": cookie}
    if authorization:
        headers["Authorization"] = authorization
    connection.request("GET", path, headers=headers)
    response = connection.getresponse()
    body = response.read()
    result = (response.status, body)
    connection.close()
    return result


def main() -> None:
    version_file = ROOT / "config/versions.env"
    pins = {}
    for line in version_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            pins[key] = value
    image = pins["HADES_NGINX_IMAGE"]
    assert "@sha256:" in image

    webui = _serve(WebUiFixture)
    agent_zero = _serve(AgentZeroFixture)
    auth = _serve(AuthFixture)
    front_webui, front_operator = _free_port(), _free_port()
    ports = {
        "@WEBUI_FRONT_PORT@": str(front_webui),
        "@OPERATOR_FRONT_PORT@": str(front_operator),
        "@WEBUI_UPSTREAM_PORT@": str(webui.server_port),
        "@AGENT_ZERO_UPSTREAM_PORT@": str(agent_zero.server_port),
        "@AUTH_PORT@": str(auth.server_port),
    }
    container_name = f"hades-operator-proxy-test-{os.getpid()}"
    container_id = ""
    with tempfile.TemporaryDirectory(prefix="hades-operator-proxy-") as temp_dir:
        config = Path(temp_dir) / "nginx.conf"
        rendered = (ROOT / "deploy/templates/agent-zero-operator.nginx.conf.in").read_text()
        for marker, value in ports.items():
            rendered = rendered.replace(marker, value)
        config.write_text(rendered)
        command = [
            "docker", "run", "-d", "--rm", "--network", "host", "--name", container_name,
            "--user", "101:101", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
            "-v", f"{config}:/tmp/nginx.conf:ro,Z", "--entrypoint", "nginx", image,
            "-c", "/tmp/nginx.conf",
        ]
        try:
            container_id = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                try:
                    status, _ = _request(front_webui, "/ready", "")
                    if status == 200:
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise AssertionError("Nginx gateway did not become ready")

            mixed = "token=owner-token; session_runtime-01=agent-session; csrf_token_runtime-01=agent-csrf; ui_pref=dark"
            status, _ = _request(front_webui, "/webui-path", mixed)
            assert status == 200
            status, body = _request(front_operator, "/index.html", mixed, "Bearer owner-token")
            assert status == 200 and b"agent-zero" in body, (status, body, auth_failures)
            with observed_lock:
                webui_request = next(item for item in observed["webui"] if item["path"] == "/webui-path")
                agent_request = next(item for item in observed["agent_zero"] if item["path"] == "/index.html")
            assert webui_request["cookie"] == "token=owner-token; ui_pref=dark", webui_request
            assert agent_request["cookie"] == "session_runtime-01=agent-session; csrf_token_runtime-01=agent-csrf", agent_request
            assert agent_request["authorization"] == "" and agent_request["user"] == "" and agent_request["groups"] == "", agent_request

            before_denial = len(observed["agent_zero"])
            status, _ = _request(front_operator, "/index.html", "token=household-token")
            assert status == 401
            assert len(observed["agent_zero"]) == before_denial

            # The same current-directory check is made on the WebSocket
            # handshake; owner revocation prevents the next handshake.
            sock = socket.create_connection(("127.0.0.1", front_operator), timeout=3)
            ws_key = base64.b64encode(os.urandom(16)).decode()
            sock.sendall((
                f"GET /socket.io/?transport=websocket HTTP/1.1\r\nHost: localhost:{front_operator}\r\n"
                "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {ws_key}\r\nSec-WebSocket-Version: 13\r\nCookie: {mixed}\r\n\r\n"
            ).encode())
            received = b""
            while b"\r\n\r\n" not in received:
                received += sock.recv(4096)
            assert received.startswith(b"HTTP/1.1 101"), received[:200]
            while not received.endswith(b"\x81\x02OK"):
                received += sock.recv(4096)
            assert received.endswith(b"\x81\x02OK"), received[-16:]
            sock.close()
            directory_role["owner-subject"] = "household"
            status, _ = _request(front_operator, "/index.html", mixed)
            assert status == 401
            directory_role["owner-subject"] = "owner"
            print("PASS dual-port Nginx route preserves root-relative UI paths and WebSocket upgrade")
            print("PASS Open WebUI cookies never reach Agent Zero and Agent Zero cookies never reach Open WebUI")
            print("PASS owner session is checked on each HTTP/WebSocket handshake; household and revoked owner fail closed")
            print("PASS pinned Nginx container runs read-only with loopback-only listeners")
        finally:
            if container_id:
                subprocess.run(["docker", "stop", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    for server in (auth, agent_zero, webui):
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
