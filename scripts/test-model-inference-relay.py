#!/usr/bin/env python3
"""Focused policy tests for the fixed-destination coding inference relay."""

from __future__ import annotations

import http.client
import json
import socket
import socketserver
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_inference_relay import RelayError, UnixHTTPServer, make_handler, parse_upstream  # noqa: E402


class RelayPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hades-inference-relay-test-")
        self.socket_path = Path(self.temp.name) / "relay.sock"
        self.server = UnixHTTPServer(
            str(self.socket_path), make_handler("198.18.0.67", 11437, "fixture-model")
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, request: bytes) -> tuple[int, bytes]:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(2)
        client.connect(str(self.socket_path))
        client.sendall(request)
        data = bytearray()
        while True:
            try:
                chunk = client.recv(65536)
            except ConnectionResetError:
                break
            if not chunk:
                break
            data.extend(chunk)
        client.close()
        header, _, body = bytes(data).partition(b"\r\n\r\n")
        status = int(header.split(b"\r\n", 1)[0].split()[1])
        return status, body

    def test_only_fixed_private_ip_upstream_is_accepted(self) -> None:
        self.assertEqual(parse_upstream("http://198.18.0.67:11437/v1"), ("198.18.0.67", 11437))
        for value in (
            "https://198.18.0.67:11437/v1",
            "http://model-service.test:11437/v1",
            "http://1.1.1.1:443/v1",
            "http://127.0.0.1:11437/v1",
            "http://224.0.0.1:11437/v1",
            "http://169.254.1.1:11437/v1",
            "http://198.18.0.67:11437/v1?target=other",
        ):
            with self.subTest(value=value), self.assertRaises(RelayError):
                parse_upstream(value)

    def test_inference_request_uses_only_fixed_model_and_path(self) -> None:
        seen = []

        class FakeResponse:
            status = 200

            @staticmethod
            def read(_limit: int) -> bytes:
                return b'{"choices":[]}'

            @staticmethod
            def getheader(name: str, default: str = "") -> str:
                return "application/json" if name == "Content-Type" else default

        class FakeConnection:
            def __init__(self, host: str, port: int, timeout: int) -> None:
                seen.append(("target", host, port, timeout))

            def request(self, method: str, path: str, body: bytes, headers: dict[str, str]) -> None:
                seen.append(("request", method, path, json.loads(body), headers))

            @staticmethod
            def getresponse() -> FakeResponse:
                return FakeResponse()

            @staticmethod
            def close() -> None:
                return

        body = json.dumps({"model": "fixture-model", "messages": [{"role": "user", "content": "fix test"}]}).encode()
        request = (b"POST /v1/chat/completions HTTP/1.1\r\nHost: untrusted.invalid\r\n"
                   b"X-Forwarded-Host: 1.1.1.1\r\nContent-Type: application/json\r\n"
                   + f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        with patch.object(http.client, "HTTPConnection", FakeConnection):
            status, response = self.request(request)
        self.assertEqual(status, 200)
        self.assertEqual(response, b'{"choices":[]}')
        self.assertEqual(seen[0], ("target", "198.18.0.67", 11437, 300))
        self.assertEqual(seen[1][1:3], ("POST", "/v1/chat/completions"))
        self.assertEqual(seen[1][3]["model"], "fixture-model")
        self.assertEqual(seen[1][4], {"Content-Type": "application/json", "Connection": "close"})

    def test_non_inference_routes_models_and_streaming_are_denied(self) -> None:
        with patch.object(http.client, "HTTPConnection") as upstream:
            self.assertEqual(self.request(b"GET /api/delete HTTP/1.1\r\nHost: local\r\n\r\n")[0], 403)
            self.assertEqual(self.request(b"GET /v1/models HTTP/1.1\r\nHost: local\r\n\r\n")[0], 403)
            body = json.dumps({"model": "other", "messages": []}).encode()
            wrong_model = (b"POST /v1/chat/completions HTTP/1.1\r\nHost: local\r\n"
                           + f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
            self.assertEqual(self.request(wrong_model)[0], 403)
            body = json.dumps({"model": "fixture-model", "stream": True, "messages": []}).encode()
            streaming = (b"POST /v1/chat/completions HTTP/1.1\r\nHost: local\r\n"
                         + f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
            self.assertEqual(self.request(streaming)[0], 403)
            self.assertFalse(upstream.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
