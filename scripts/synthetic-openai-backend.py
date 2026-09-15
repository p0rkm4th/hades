#!/usr/bin/env python3
"""Tiny OpenAI-compatible backend for the isolated application fixture."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time

MODEL = "synthetic-reconstruction-model"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _send(self, body, status=200):
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/v1/models":
            self._send({"data": [{"id": MODEL, "object": "model", "owned_by": "synthetic"}]})
            return
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self._send({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        user = next(
            (message.get("content", "") for message in request.get("messages", [])
             if message.get("role") == "user"),
            "",
        )
        self._send({
            "id": "synthetic-reconstruction-completion",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": MODEL,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": f"Synthetic application response: {user}"},
                "finish_reason": "stop",
            }],
        })


ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
