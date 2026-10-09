#!/usr/bin/env python3
"""Contract for optional authenticated Hermes transcript continuation."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "hades_owner_subset_benchmark",
    ROOT / "scripts/benchmark-hades-owner-subset.py",
)
if spec is None or spec.loader is None:
    raise SystemExit("could not load owner-subset benchmark helpers")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

requests: list[dict[str, object]] = []


class FakeResponse:
    status = 200

    def __init__(self):
        self.lines = [
            b'data: {"choices":[{"delta":{"content":"Okay."},"finish_reason":null}]}\n',
            b"data: [DONE]\n",
        ]

    def readline(self):
        return self.lines.pop(0) if self.lines else b""


class FakeConnection:
    def __init__(self, *_args, **_kwargs):
        pass

    def request(self, method, path, *, body, headers):
        requests.append({
            "method": method,
            "path": path,
            "body": json.loads(body),
            "headers": dict(headers),
        })

    def getresponse(self):
        return FakeResponse()

    def close(self):
        pass


original = module.http.client.HTTPConnection
module.http.client.HTTPConnection = FakeConnection
try:
    continued = module.chat(
        1234, "hades", "continuation-contract",
        [{"role": "user", "content": "Where did I move?"}], 32,
        session_id="synthetic-session-01",
    )
    fresh = module.chat(
        1234, "hades", "fresh-contract",
        [{"role": "user", "content": "Hi."}], 32,
    )
finally:
    module.http.client.HTTPConnection = original

assert continued["answer"] == "Okay."
assert requests[0]["headers"].get("X-Hermes-Session-Id") == "synthetic-session-01"
assert requests[0]["headers"].get("X-Hermes-Session-Key") == "hades-user-hades-synthetic"
assert "X-Hermes-Session-Id" not in requests[1]["headers"]
assert fresh["answer"] == "Okay."
print("PASS optional X-Hermes-Session-Id is sent only for explicit continuation")
