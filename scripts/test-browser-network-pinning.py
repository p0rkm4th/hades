#!/usr/bin/env python3
"""Exercise browser-proxy DNS pinning and HTTP write rejection locally."""

import importlib.util
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import threading


spec = importlib.util.spec_from_file_location(
    "hades_browser_proxy", Path("integrations/browser-access/proxy.py")
)
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)

requests = []


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        requests.append((self.command, self.path))
        body = b"pinned"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        requests.append((self.command, self.path))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_args):
        pass


fixture = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
threading.Thread(target=fixture.serve_forever, daemon=True).start()
original_resolver = socket.getaddrinfo
resolved = []


def changing_resolver(host, port, *args, **kwargs):
    if host == "rebinding.example.test":
        resolved.append(host)
        ip = "127.0.0.1" if len(resolved) == 1 else "203.0.113.9"
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]
    return original_resolver(host, port, *args, **kwargs)


socket.getaddrinfo = changing_resolver
os.environ["HADES_BROWSER_ALLOW_PRIVATE_TARGETS"] = "1"  # only the local fixture
filtered = proxy._FilteringProxy(("rebinding.example.test",))
try:
    for method in ("GET", "POST"):
        client = socket.create_connection(("127.0.0.1", filtered.port), timeout=5)
        path = f"http://rebinding.example.test:{fixture.server_port}/probe"
        client.sendall(
            f"{method} {path} HTTP/1.1\r\nHost: rebinding.example.test:{fixture.server_port}\r\nConnection: close\r\n\r\n".encode()
        )
        response = bytearray()
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            response.extend(chunk)
        client.close()
        status = bytes(response).split(b"\r\n", 1)[0]
        if method == "GET":
            assert status.startswith(b"HTTP/1.0 200"), status
            assert b"pinned" in response
        else:
            assert status.startswith(b"HTTP/1.0 403"), status
    assert resolved == ["rebinding.example.test"], resolved
    assert requests == [("GET", "/probe")], requests
    print("PASS browser proxy pins the single validated DNS answer for its connection")
    print("PASS browser proxy rejects HTTP POST before the fixture receives it")
finally:
    filtered.close()
    fixture.shutdown()
    fixture.server_close()
    socket.getaddrinfo = original_resolver
