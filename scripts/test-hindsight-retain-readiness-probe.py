#!/usr/bin/env python3
"""Contract for the benchmark-only bank-scoped retain readiness probe."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import urllib.error
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "hades_memory_pair_benchmark",
    ROOT / "scripts/benchmark-hades-memory-pair.py",
)
if spec is None or spec.loader is None:
    raise SystemExit("could not load paired benchmark helpers")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

payloads = iter([
    {"operations": [{"status": "pending", "task_type": "retain"}]},
    {"operations": []},
    {"operations": []},
    {"operations": []},
    {"operations": []},
    {"operations": []},
])
seen = []


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __enter_bytes(self):
        return json.dumps(self.payload).encode()

    def read(self):
        return self.__enter_bytes()


def fake_urlopen(url, timeout):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    seen.append((parsed.path, query, timeout))
    return Response(next(payloads))


original_urlopen = module.urllib.request.urlopen
original_sleep = module.time.sleep
module.urllib.request.urlopen = fake_urlopen
module.time.sleep = lambda _delay: None
try:
    result = module.wait_hindsight_retains(
        "http://127.0.0.1:8888", "synthetic-owner-bank", timeout=1
    )
finally:
    module.urllib.request.urlopen = original_urlopen
    module.time.sleep = original_sleep

assert result["ready"] is True, result
assert result["polls"] == 3, result
assert result["max_active_retains"] == 1, result
assert all(row[1]["type"] == ["retain"] and row[1]["limit"] == ["100"] for row in seen)
assert all("synthetic-owner-bank" in row[0] for row in seen)

print("PASS bank-scoped retain readiness requires two empty status observations and retains only aggregate counts")
