#!/usr/bin/env python3
"""Check paired workspace benchmarks reset and seed Ollama equally per arm."""
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "workspace_pair_benchmark",
    ROOT / "scripts" / "benchmark-hades-workspace-read-pair.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

assert MODULE.common_prefix_byte_count(b"shared-a", b"shared-b") == len(b"shared-")
assert MODULE.common_prefix_byte_count(b"same", b"same") == 4
assert MODULE.common_prefix_byte_count(b"", b"not empty") == 0
assert MODULE.EXPLAIN_PROMPT == "In discount.py, explain what discounted_total does in plain English."
assert MODULE.FIXTURE_CASES["discount"]["source"] == "discount.py"
assert "return price - percent" in MODULE.FIXTURE_CASES["discount"]["source_content"]

digest = "sha256:" + "a" * 64
image = f"nikolaik/python-nodejs@{digest}"
image_id = "sha256:" + "b" * 64
def fake_image_lookup(command, *, text, stderr=None):
    if command[1:3] == ["image", "inspect"]:
        raise subprocess.CalledProcessError(1, command)
    assert command[1:4] == ["image", "ls", "--digests"]
    return f"other/repo@{digest} sha256:{'c' * 64}\nnikolaik/python-nodejs@{digest} {image_id}\n"

with patch.object(MODULE.subprocess, "check_output", side_effect=fake_image_lookup):
    assert MODULE.inspect_sandbox_image_id("docker", image) == image_id
with patch.object(MODULE.subprocess, "check_output", side_effect=fake_image_lookup):
    try:
        MODULE.inspect_sandbox_image_id("docker", f"missing/repo@{digest}")
    except RuntimeError as exc:
        assert "exact pinned sandbox digest" in str(exc)
    else:
        raise AssertionError("accepted a different locally available sandbox digest")
try:
    MODULE.inspect_sandbox_image_id("docker", "nikolaik/python-nodejs:latest")
except RuntimeError as exc:
    assert "immutable sha256 digest" in str(exc)
else:
    raise AssertionError("accepted a mutable sandbox tag")

calls: list[tuple[str, dict | None]] = []
warmed = False


def fake_local_json(url: str, payload: dict | None = None, *, timeout: float = 10):
    global warmed
    calls.append((url, payload))
    if url.endswith("/api/chat"):
        assert payload == {
            "model": MODULE.MODEL,
            "messages": [],
            "keep_alive": 0,
        }
        return {"done_reason": "unload"}
    if url.endswith("/api/generate"):
        assert payload == {
            "model": MODULE.MODEL,
            "prompt": "hi",
            "stream": False,
            "options": {"num_ctx": 65536, "num_predict": 4},
        }
        warmed = True
        return {"done": True}
    if url.endswith("/api/ps"):
        return {
            "models": ([{"name": MODULE.MODEL, "context_length": 65536}] if warmed else [])
        }
    raise AssertionError(f"Unexpected local endpoint: {url}")


MODULE.local_json = fake_local_json
assert MODULE.reset_and_warm_model("http://127.0.0.1:11445") == 65536
assert [url.rsplit("/", 1)[-1] for url, _ in calls] == ["chat", "ps", "generate", "ps"]

MODULE.local_json = lambda *_args, **_kwargs: {"done_reason": "stop"}
try:
    MODULE.reset_and_warm_model("http://127.0.0.1:11445")
except RuntimeError as exc:
    assert "did not confirm model unload" in str(exc)
else:
    raise AssertionError("Benchmark accepted an unconfirmed cache reset")

print("PASS paired arms receive a verified Ollama unload and identical context warmup")
print("PASS cache diagnostics retain prefix lengths only, not prefix content")
