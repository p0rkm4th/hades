#!/usr/bin/env python3
"""Local extraction-model stub for disposable Hindsight UI acceptance only."""
from __future__ import annotations

import http.server
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path


bind_address, port_file, request_log = sys.argv[1:4]
model = os.environ.get("HADES_SYNTHETIC_HINDSIGHT_MODEL", "synthetic-hindsight-ui-extractor")
fact = "The synthetic user prefers violet comet-42 markers."
fact_response = json.dumps({
    "facts": [{
        "what": fact,
        "when": "N/A",
        "where": "N/A",
        "who": "user",
        "why": "Explicit synthetic acceptance fact.",
        "fact_type": "world",
        "entities": ["user", "violet comet-42 markers"],
    }],
})


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        # Retain only route/model metadata; prompt and completion content are
        # synthetic and deliberately never written to the harness log.
        with Path(request_log).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"path": self.path, "model": str(body.get("model", ""))}) + "\n")
        if self.path.endswith("/v1/embeddings"):
            raw_input = body.get("input", "")
            texts = raw_input if isinstance(raw_input, list) else [raw_input]
            if not all(isinstance(text, str) for text in texts):
                self.send_error(400)
                return
            response = {
                "object": "list",
                "model": model,
                "data": [{
                    "object": "embedding",
                    "index": index,
                    "embedding": synthetic_embedding(text),
                } for index, text in enumerate(texts)],
                "usage": {
                    "prompt_tokens": sum(len(text.split()) for text in texts),
                    "total_tokens": sum(len(text.split()) for text in texts),
                },
            }
        elif self.path.endswith("/api/chat"):
            response = {
                "model": model,
                "message": {"role": "assistant", "content": fact_response},
                "done": True,
            }
        elif self.path.endswith("/v1/chat/completions"):
            response = {
                "id": "synthetic-hindsight-ui",
                "object": "chat.completion",
                "created": 1,
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": fact_response},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            }
        else:
            self.send_error(404)
            return
        payload = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args: object) -> None:
        return


def synthetic_embedding(text: str, dimensions: int = 384) -> list[float]:
    """Stable local feature-hash vectors for synthetic backup/restore fixtures."""
    tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.casefold())
    features = tokens + [f"{left} {right}" for left, right in zip(tokens, tokens[1:])]
    vector = [0.0] * dimensions
    for feature in features:
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return vector


server = http.server.ThreadingHTTPServer((bind_address, 0), Handler)
Path(port_file).write_text(str(server.server_address[1]), encoding="ascii")
server.serve_forever()
